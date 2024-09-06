# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

# (c) Meta Platforms, Inc. and affiliates. Confidential and proprietary.

from unittest import mock

import pytest
import torch
from torchtune.data import (
    left_pad_sequence,
    padded_collate,
    padded_collate_dpo,
    padded_collate_packed,
    padded_collate_sft,
)
from torchtune.modules.attention_utils import _SUPPORTS_FLEX_ATTENTION


class TestPaddedCollateSFT:
    def test_batch_pad_sequence(self):
        """
        Tests that shorter input, label sequences are padded to the max seq len.
        """
        padding_idx = -8
        ignore_idx = -9
        token_pairs = [
            {
                "tokens": [1, 2, 3],
                "labels": [4, 5, 6],
            },
            {
                "tokens": [7],
                "labels": [10],
            },
        ]
        padded = padded_collate_sft(
            batch=token_pairs,
            device="cpu",
            padding_idx=padding_idx,
            ignore_idx=ignore_idx,
        )
        padded_input = padded["tokens"][1]
        padded_label = padded["labels"][1]
        torch.testing.assert_close(
            padded_input, torch.tensor([7, padding_idx, padding_idx])
        )
        torch.testing.assert_close(
            padded_label, torch.tensor([10, ignore_idx, ignore_idx])
        )

    @mock.patch("torchtune.modules.attention_utils.torch_version_ge")
    def test_padded_collate_packed_sdpa(self, mock_version):
        mock_version.return_value = False
        token_pairs = [
            {
                "tokens": torch.tensor([1, 2, 3, 4, 5, 6]),
                "labels": torch.tensor([7, 8, 9, 10, 11, 12]),
                "input_pos": torch.tensor([0, 1, 2, 0, 1, 0]),
                "seq_lens": torch.tensor([3, 2, 1]),
            },
            {
                "tokens": torch.tensor([13, 14, 15, 16, 17, 18]),
                "labels": torch.tensor([19, 20, 21, 22, 23, 24]),
                "input_pos": torch.tensor([0, 1, 0, 1, 0, 1]),
                "seq_lens": torch.tensor([2, 2, 2]),
            },
        ]
        collated = padded_collate_packed(
            batch=token_pairs,
            device="cpu",
        )
        torch.testing.assert_close(
            collated["tokens"],
            torch.tensor([[1, 2, 3, 4, 5, 6], [13, 14, 15, 16, 17, 18]]),
        )
        torch.testing.assert_close(
            collated["labels"],
            torch.tensor([[7, 8, 9, 10, 11, 12], [19, 20, 21, 22, 23, 24]]),
        )
        torch.testing.assert_close(
            collated["input_pos"],
            torch.tensor([[0, 1, 2, 0, 1, 0], [0, 1, 0, 1, 0, 1]]),
        )
        torch.testing.assert_close(
            collated["mask"],
            torch.tensor(
                [
                    [
                        [1, 0, 0, 0, 0, 0],
                        [1, 1, 0, 0, 0, 0],
                        [1, 1, 1, 0, 0, 0],
                        [0, 0, 0, 1, 0, 0],
                        [0, 0, 0, 1, 1, 0],
                        [0, 0, 0, 0, 0, 1],
                    ],
                    [
                        [1, 0, 0, 0, 0, 0],
                        [1, 1, 0, 0, 0, 0],
                        [0, 0, 1, 0, 0, 0],
                        [0, 0, 1, 1, 0, 0],
                        [0, 0, 0, 0, 1, 0],
                        [0, 0, 0, 0, 1, 1],
                    ],
                ],
                dtype=torch.bool,
            ),
        )

    @pytest.mark.skipif(
        not _SUPPORTS_FLEX_ATTENTION,
        reason="Please install a nightly build of torch to run this test.",
    )
    def test_padded_collate_packed_flex(self):
        # create_block_mask requires that seq_len be divisible by 128, the default block size.
        # see https://github.com/pytorch/pytorch/blob/main/torch/nn/attention/flex_attention.py#L636
        batch = [
            {
                "tokens": torch.ones(128, dtype=torch.long),
                "labels": torch.ones(128, dtype=torch.long),
                "input_pos": torch.zeros(128, dtype=torch.long),
                "seq_lens": torch.ones(64, dtype=torch.long) * 2,
            },
            {
                "tokens": torch.ones(128, dtype=torch.long),
                "labels": torch.ones(128, dtype=torch.long),
                "input_pos": torch.zeros(128, dtype=torch.long),
                "seq_lens": torch.ones(32, dtype=torch.long) * 4,
            },
        ]
        collated = padded_collate_packed(
            batch=batch,
            device="cpu",
        )
        torch.testing.assert_close(
            collated["tokens"], torch.stack([torch.ones(128), torch.ones(128)])
        )
        torch.testing.assert_close(
            collated["labels"], torch.stack([torch.ones(128), torch.ones(128)])
        )
        torch.testing.assert_close(
            collated["input_pos"], torch.stack([torch.zeros(128), torch.zeros(128)])
        )
        torch.testing.assert_close(
            collated["mask"],
            torch.tensor([[[[1]]], [[[1]]]], dtype=torch.long),
        )


class TestLeftPadSequence:
    def test_left_pad_sequence(self):
        a = torch.tensor([1, 2, 3])
        b = torch.tensor([4, 5, 6, 7])
        c = torch.tensor([8, 9, 10, 11, 12])
        result = left_pad_sequence([a, b, c], batch_first=True, padding_value=0)
        expected = torch.tensor([[0, 0, 1, 2, 3], [0, 4, 5, 6, 7], [8, 9, 10, 11, 12]])
        assert torch.equal(result, expected)


class TestPaddedCollate:
    def test_padded_collate_classifier_labels(self):
        batch = [
            {"tokens": [1, 2, 3], "labels": 1},
            {"tokens": [4, 5], "labels": 2},
            {"tokens": [6, 7, 8, 9], "labels": 3},
        ]
        result = padded_collate(
            batch,
            pad_direction="right",
            keys_to_pad=["tokens"],
            padding_idx=-10,
        )
        expected_tokens = torch.tensor([[1, 2, 3, -10], [4, 5, -10, -10], [6, 7, 8, 9]])
        expected_labels = torch.tensor([1, 2, 3])
        assert torch.equal(result["tokens"], expected_tokens)
        assert torch.equal(result["labels"], expected_labels)

    def test_padded_collate_multiple_keys_to_pad(self):
        batch = [
            {"tokens": [1, 2], "labels_0": [3, 4], "labels_1": 1},
            {"tokens": [5, 6, 7], "labels_0": [8, 9, 10], "labels_1": 2},
        ]
        result = padded_collate(
            batch,
            pad_direction="left",
            keys_to_pad=["tokens", "labels_0"],
            padding_idx={"tokens": 0, "labels_0": -1},
        )
        expected_tokens = torch.tensor([[0, 1, 2], [5, 6, 7]])
        expected_labels_0 = torch.tensor([[-1, 3, 4], [8, 9, 10]])
        expected_labels_1 = torch.tensor([1, 2])
        assert torch.equal(result["tokens"], expected_tokens)
        assert torch.equal(result["labels_0"], expected_labels_0)
        assert torch.equal(result["labels_1"], expected_labels_1)

    def test_value_error_raised_when_empty_keys_to_pad(self):
        batch = [{"labels": [1]}, {"labels": [2]}]
        with pytest.raises(ValueError):
            padded_collate(batch, pad_direction="left", keys_to_pad=[], padding_idx=0)

    def test_value_error_raised_when_mismatched_padding_idx_keys(self):
        batch = [{"tokens": [1, 2], "labels": [1, 1]}]
        with pytest.raises(ValueError):
            padded_collate(
                batch,
                pad_direction="left",
                keys_to_pad=["tokens", "labels"],
                padding_idx={"tokens": 0},
            )

    def test_value_error_raised_when_mismatched_keys_to_pad(self):
        batch = [{"tokens": [1, 2], "labels": [1, 1]}]
        with pytest.raises(ValueError):
            padded_collate(
                batch,
                pad_direction="left",
                keys_to_pad=["tokens", "labels_0"],
                padding_idx={"tokens": 0},
            )

    def test_value_error_raised_when_invalid_pad_direction(self):
        batch = [{"tokens": [1, 2], "labels": [1, 1]}]
        with pytest.raises(ValueError):
            padded_collate(
                batch,
                pad_direction="oogabooga",
                keys_to_pad=["tokens", "labels_0"],
                padding_idx={"tokens": 0},
            )


class TestPaddedCollateDPO:
    def test_dpo_collate(self):
        batch = [
            {
                "chosen_input_ids": [1, 2, 3],
                "chosen_labels": [4, 5, 6],
                "rejected_input_ids": [7, 8],
                "rejected_labels": [9, 10],
            },
            {
                "chosen_input_ids": [11, 12],
                "chosen_labels": [13, 14],
                "rejected_input_ids": [15, 16, 17],
                "rejected_labels": [18, 19, 20],
            },
        ]
        input_ids, labels = padded_collate_dpo(batch, padding_idx=0, ignore_idx=-100)
        expected_input_ids = torch.tensor(
            [[1, 2, 3], [11, 12, 0], [7, 8, 0], [15, 16, 17]]
        )
        expected_labels = torch.tensor(
            [[4, 5, 6], [13, 14, -100], [9, 10, -100], [18, 19, 20]]
        )
        assert torch.equal(input_ids, expected_input_ids)
        assert torch.equal(labels, expected_labels)
