# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import logging
from typing import Callable, Optional, Union

import torch

from torch import nn
from torchtune.utils._version import torch_version_ge
from torchtune.utils.logging import get_logger, log_once

# We can only use flex attention / BlockMask if torch version >= 2.5.0 and GPU is Turing / SM75 and above
_SUPPORTS_FLEX_ATTENTION = torch_version_ge(
    "2.5.0"
) and torch.cuda.get_device_capability() >= (7, 5)

if _SUPPORTS_FLEX_ATTENTION:
    from torch.nn.attention.flex_attention import (
        BlockMask,
        create_block_mask as create_block_causal_mask_flex,
        flex_attention,
    )

    _MaskType = Union[torch.Tensor, BlockMask]
else:
    _MaskType = torch.Tensor

_log: logging.Logger = get_logger()


def _get_document_ids_from_seq_lens(
    seq_lens: torch.Tensor,
) -> torch.Tensor:
    """
    Convert a batch tensor of seq lens into integer IDs denoting sample ownership.
    For example, seq_lens = [2, 3, 1] would return [0, 0, 1, 1, 1, 2].

    Args:
        seq_lens (torch.Tensor): Sequence lengths of samples in each pack in the batch,
            shape (batch_size, n), where n is the max number of sequences across packs.

    Returns:
        Tensor: Document IDs of shape (batch_size, max_seq_len).
    """
    batch_size = seq_lens.shape[0]
    batch_document_ids = []
    for sample_idx in range(batch_size):
        # We assume seq lens sum to max seq lens, so document_ids should be of
        # shape (max_seq_len, )
        document_ids = torch.cat(
            [
                torch.full((seq_len,), i, dtype=torch.long, device=seq_lens.device)
                for i, seq_len in enumerate(seq_lens[sample_idx])
            ]
        )
        batch_document_ids.append(document_ids)
    batch_document_ids = torch.stack(batch_document_ids)
    return batch_document_ids


def create_block_causal_mask(seq_lens: torch.Tensor) -> torch.Tensor:
    """
    Given a batch tensor of seq lens defining the lengths of samples in each pack,
    Construct a 2D block causal mask for each pack in the batch. For example, if
    a single sample's seq_lens is [3, 2, 1], the mask would be::

        mask = [
            [1, 0, 0, 0, 0, 0],
            [1, 1, 0, 0, 0, 0],
            [1, 1, 1, 0, 0, 0],
            [0, 0, 0, 1, 0, 0],
            [0, 0, 0, 1, 1, 0],
            [0, 0, 0, 0, 0, 1],
        ]

    Args:
        seq_lens (torch.Tensor): Sequence lengths of samples in each pack in the batch,
            shape (batch_size, n), where n is the max number of sequences across packs.

    Returns:
        Tensor: Block causal mask of shape (batch_size, max_seq_len, max_seq_len).
    """
    batch_block_attn_masks = []
    batch_size = seq_lens.shape[0]
    for sample_idx in range(batch_size):
        block_attn_masks = [
            torch.tril(
                torch.ones(seq_len, seq_len, dtype=torch.bool, device=seq_lens.device)
            )
            for i, seq_len in enumerate(seq_lens[sample_idx])
        ]

        batch_block_attn_masks.append(torch.block_diag(*block_attn_masks))
    return torch.stack(batch_block_attn_masks)


def packed_block_causal_mask(
    seq_lens: torch.Tensor,
) -> _MaskType:
    """
    Create a block causal document mask for a batch of packed sequences. If on
    torch version >= 2.5.0, this is done by creating a mask_mod function with the
    block causal logic and passing this into :func:`torch.nn.attention.flex_attention.create_block_mask`.
    The resultant BlockMask is a compressed representation of the full block causal
    mask. If on an older version, a standard 2D block causal mask is created and returned.

    Args:
        seq_lens (torch.Tensor): Sequence lengths of samples in each pack in the batch,
            shape (batch_size, n), where n is the max number of sequences across packs.

    Returns:
        _MaskType: BlockMask or Tensor if torch version < 2.5.0.
    """
    if _SUPPORTS_FLEX_ATTENTION:
        document_ids = _get_document_ids_from_seq_lens(seq_lens)
        batch_size, max_seq_len = document_ids.shape
        document_ids = document_ids.to("cuda")

        def mask_mod(b, h, q_idx, kv_idx):
            causal_mask = q_idx >= kv_idx
            document_mask = document_ids[b, q_idx] == document_ids[b, kv_idx]
            return causal_mask & document_mask

        return create_block_causal_mask_flex(
            mask_mod,
            batch_size,
            None,
            max_seq_len,
            max_seq_len,
        )
    else:
        return create_block_causal_mask(seq_lens=seq_lens)


def _sdpa_or_flex_attention() -> Callable:
    """
    Helper function to decide when to call flex attention or SDPA. It will use
    flex attention if ALL of the following conditions are met, otherwise it will
    default to SDPA:
    - torch version >= 2.5.0
    - we are sample packing, therefore mask is a BlockMask
    - torch.cuda.get_device_capability() >= (7, 5)
    """

    if _SUPPORTS_FLEX_ATTENTION:
        flex_attention_compiled = torch.compile(flex_attention, dynamic=False)

        def _attention_call(
            q: torch.Tensor,
            k: torch.Tensor,
            v: torch.Tensor,
            mask: Optional[_MaskType],
            dropout_p: float,
            is_causal: bool,
        ) -> torch.Tensor:

            # Flex attention uses the BlockMask
            # (https://github.com/pytorch/pytorch/blob/main/torch/nn/attention/flex_attention.py#L168)
            # instead of a traditional boolean tensor mask. If this is passed in,
            # we assume the user wants to use flex attention instead of traditional SDPA.
            # This will use flash attention under the hood with support for custom masks.
            # Currently, it is used when sample packing is enabled (see torchtune.datasets.PackedDataset)
            if isinstance(mask, BlockMask):
                log_once(
                    _log,
                    "Using flex attention for attention computation since a BlockMask was passed in.",
                    level=logging.DEBUG,
                )
                return flex_attention_compiled(
                    q,
                    k,
                    v,
                    block_mask=mask,
                )
            # If mask is a standard boolean tensor or None, then use SDPA
            else:
                # shape: [b, 1, s, s]
                if mask is not None:
                    mask = mask[:, None, :, :]

                # Flash attention from https://pytorch.org/blog/accelerating-large-language-models/
                return nn.functional.scaled_dot_product_attention(
                    q,
                    k,
                    v,
                    attn_mask=mask,
                    dropout_p=dropout_p,
                    is_causal=is_causal,
                )

    else:

        def _attention_call(
            q: torch.Tensor,
            k: torch.Tensor,
            v: torch.Tensor,
            mask: Optional[_MaskType],
            dropout_p: float,
            is_causal: bool,
        ) -> torch.Tensor:
            # shape: [b, 1, s, s]
            if mask is not None:
                mask = mask[:, None, :, :]

            # Flash attention from https://pytorch.org/blog/accelerating-large-language-models/
            return nn.functional.scaled_dot_product_attention(
                q,
                k,
                v,
                attn_mask=mask,
                dropout_p=dropout_p,
                is_causal=is_causal,
            )

    return _attention_call