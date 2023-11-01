# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from typing import Optional

from torch import nn, Tensor

from llm.llama2.position_embeddings import RotaryPositionalEmbeddings


class LlamaSelfAttention(nn.Module):
    """
    Multi-headed grouped query self-attention (GQA) layer introduced
    in https://arxiv.org/pdf/2305.13245v1.pdf

    GQA is a version of multiheaded attention (MHA) which uses fewer
    key/value heads than query heads by grouping n query heads for each
    key and value head. Multi-Query Attention is an extreme
    version where we have a single key and value head shared by all
    query heads.

    Following is an example of MHA, GQA and MQA with num_heads = 4

    (credit for the documentation:
    https://github.com/Lightning-AI/lit-gpt/blob/main/lit_gpt/config.py)


    ┌───┐┌───┐┌───┐┌───┐     ┌───┐    ┌───┐             ┌───┐
    │ v ││ v ││ v ││ v │     │ v │    │ v │             │ v │
    └───┘└───┘└───┘└───┘     └───┘    └───┘             └───┘
      │    │    │    │         │        │                 │
    ┌───┐┌───┐┌───┐┌───┐     ┌───┐    ┌───┐             ┌───┐
    │ k ││ k ││ k ││ k │     │ k │    │ k │             │ k │
    └───┘└───┘└───┘└───┘     └───┘    └───┘             └───┘
      │    │    │    │      ┌──┴──┐  ┌──┴──┐      ┌────┬──┴─┬────┐
    ┌───┐┌───┐┌───┐┌───┐  ┌───┐┌───┐┌───┐┌───┐  ┌───┐┌───┐┌───┐┌───┐
    │ q ││ q ││ q ││ q │  │ q ││ q ││ q ││ q │  │ q ││ q ││ q ││ q │
    └───┘└───┘└───┘└───┘  └───┘└───┘└───┘└───┘  └───┘└───┘└───┘└───┘
    ◀──────────────────▶  ◀──────────────────▶  ◀──────────────────▶
            MHA                    GQA                   MQA
       n_kv_heads =4          n_kv_heads=2           n_kv_heads=1

    Args:

        embed_dim (int): embedding dimension for the model
        num_heads (int): number of query heads. For MHA this is also the
            number of heads for key and value
        max_seq_len (int): maximum sequence length supported by the model.
            This is needed to compute the RoPE Cache. Default: 4096.
        num_kv_heads (Optional[int]): number of key and value heads. If specified,
            user should ensure `num_heads` % `num_kv_heads` == 0. Default value is
            `None`, in which case this is the same as MHA
        attn_dropout (float): dropout value passed onto the
            scaled_dot_product_attention function. This argument is ignored if the
            self.training is False. Default value is 0.0.

    Raises:
         ValueError: If `num_heads` % `num_kv_heads` != 0
         ValueError: If `embed_dim` % `num_heads` != 0
         ValueError: If `attn_dropout` < 0 or > 1
    """

    def __init__(
        self,
        embed_dim: int,
        num_heads: int,
        max_seq_len: int = 4096,
        num_kv_heads: Optional[int] = None,
        attn_dropout: float = 0.0,
    ) -> None:
        super().__init__()

        if num_kv_heads and num_heads % num_kv_heads != 0:
            raise ValueError(
                f"num_heads ({num_heads}) must be divisible by "
                f"num_kv_heads ({num_kv_heads})"
            )

        if embed_dim % num_heads != 0:
            raise ValueError(
                f"embed_dim ({embed_dim}) must be divisible by "
                f"num_heads ({num_heads})"
            )

        if attn_dropout < 0 or attn_dropout > 1:
            raise ValueError(f"attn_dropout ({embed_dim}) must be between 0.0 and 1.0")

        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads if num_kv_heads else num_heads
        self.embed_dim = embed_dim
        self.attn_dropout = attn_dropout
        self.head_dim = embed_dim // num_heads
        self.max_seq_len = max_seq_len

        # Output dimension of the qkv projection matrix depends on the
        # total number of heads and the dimension of each head.
        # For MHA this is simply 3 * embed_dim since num_kv_heads = num_heads
        qkv_dim = (self.num_heads + 2 * self.num_kv_heads) * self.head_dim

        self.qkv_proj = nn.Linear(self.embed_dim, qkv_dim, bias=False)
        self.output_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=False)

        # Build the RoPE cache
        self.rope = RotaryPositionalEmbeddings(
            dim=self.head_dim, max_seq_len=max_seq_len
        )

    def forward(self, x: Tensor) -> Tensor:
        """
        Args:
            x (Tensor): input tensor with shape
                [batch_size x seq_length x embed_dim]

        Returns:
            Tensor: output tensor with attention applied

        Raises:
            ValueError: if seq_len of x is bigger than max_seq_len

        Notation used for tensor shapes:
            - b: batch size
            - s: sequence length
            - n_h: num heads
            - n_kv: num kv heads
            - d: embed dim
            - h_d: head dim
            - qkv_d: qkv_dim compured as (n_h + 2 * n_kv) * h_d

        TODO: A few TODOs
            - Return the attention weights
            - Control whether we apply RoPE or not with a flag
            - Add support for KV Cache (inference)
        """

        # input has shape [b, s, d]
        bsz, seq_len, _ = x.shape

        if seq_len > self.max_seq_len:
            raise ValueError(
                f"seq_len ({seq_len}) of input tensor should be smaller "
                f"than max_seq_len ({self.max_seq_len})"
            )

        # qkv has shape [b, s, qkv_d]
        qkv = self.qkv_proj(x)

        # number of queries per key/value
        q_per_kv = self.num_heads // self.num_kv_heads

        # Each key and value either has a single query (MHA)
        # or q_per_kv queries (MQA/GQA). total_qkv will be 3
        # for MHA
        total_qkv = q_per_kv + 2

        # decompose the last dimension into n_kv x total_qkv, h_d
        qkv = qkv.view(bsz, seq_len, self.num_kv_heads, total_qkv, self.head_dim)

        # create the q,k and v tensors by splitting qkv
        # q: [b, s, n_kv, q_per_kv, h_d]
        # k: [b, s, n_kv, 1, h_d]
        # v: [b, s, n_kv, 1, h_d]
        q, k, v = qkv.split((q_per_kv, 1, 1), dim=3)

        # if needed, expand the key and value tensors to have the same shape
        # as the query tensor by copying values across the relevant dim
        if self.num_heads != self.num_kv_heads:
            k = k.expand(bsz, seq_len, self.num_kv_heads, q_per_kv, self.head_dim)
            v = v.expand(bsz, seq_len, self.num_kv_heads, q_per_kv, self.head_dim)

        # llama2 applies the RoPE embeddings on tensors with shape
        # [b, s, n_h, h_d]
        # Reshape the tensors before we apply RoPE
        q = q.reshape(bsz, seq_len, -1, self.head_dim)
        k = k.reshape(bsz, seq_len, -1, self.head_dim)
        v = k.reshape(bsz, seq_len, -1, self.head_dim)

        q = self.rope(q)
        k = self.rope(k)

        # [b, n_h, s, h_d]
        q = q.transpose(1, 2)
        k = k.transpose(1, 2)
        v = v.transpose(1, 2)

        # using SDPA from nn.functional allows us to take
        # advantage of flash attention
        # ref: https://pytorch.org/blog/accelerating-large-language-models/
        output = nn.functional.scaled_dot_product_attention(
            q,
            k,
            v,
            attn_mask=None,
            dropout_p=self.attn_dropout if self.training else 0.0,
            is_causal=True,
        )

        # reshape the output to be the same shape as the input
        output = output.transpose(1, 2).contiguous().view(bsz, seq_len, -1)
        return self.output_proj(output)