# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

from abc import ABC, abstractmethod
from typing import List

from torchtune.data._types import Message


class PromptTemplate(ABC):
    """
    Interface for prompt templates, which add flavor text to input messages by role. 
    Each prompt template should include template strings with placeholders for the data 
    inputs. There should be a template for each role: system, user, assistant.
    """

    system = ""
    user = ""
    assistant = ""

    @classmethod
    @abstractmethod
    def format(
        cls,
        sample: List[Message],
    ) -> List[Message]:
        """
        Format each role's message(s) according to the prompt template

        Args:
            sample (List[Message]): a single conversation, structured as a list
                of :class:`~torchtune.data.Message` objects

        Returns:
            The formatted list of messages
        """
        pass


class Llama2ChatTemplate(PromptTemplate):
    """
    Chat template that formats human and system prompts with appropriate tags
    used in Llama2 pre-training. Taken from Meta's official `Llama inference
    repository <https://github.com/meta-llama/llama/blob/main/llama/generation.py>`_.

    Example:
        .. code-block:: text

            "[INST] <<SYS>>
            You are a helpful, respectful and honest assistant.
            <</SYS>>"

            I am going to Paris, what should I see? [/INST] Paris, the capital of France, is known for its stunning architecture..."

    """

    B_INST, E_INST = "[INST]", "[/INST]"
    B_SYS, E_SYS = "<<SYS>>\n", "\n<</SYS>>\n\n"

    system = f"{B_SYS}{{content}}{E_SYS}"
    user = f"{B_INST} {{system_message}}{{content}} {E_INST} "
    assistant = ""

    @classmethod
    def format(
        cls,
        sample: List[Message],
    ) -> List[Message]:
        """
        Format user and system messages with appropriate tags.

        Args:
            sample (List[Message]): a single conversation, structured as a list
                of :class:`~torchtune.data.Message` objects

        Returns:
            The formatted list of messages
        """
        system_message = ""
        formatted_dialogue = []
        for message in sample:
            content = ""
            if message.role == "system":
                content = cls.system.format(content=message.content)
                system_message = content
                # Incorporate the system message in the user message - Llama2 only
                # looks for the <<SYS>> tags and not the explicit role so this will
                # be treated the same as an actual system message. We do this because
                # of the nesting of the system prompt in the user message.
                continue
            elif message.role == "user":
                content = cls.user.format(
                    system_message=system_message, content=message.content
                )
            elif message.role == "assistant":
                # No special formatting needed for assistant message
                content = message.content
            formatted_dialogue.append(
                Message(role=message.role, content=content, masked=message.masked),
            )
        return formatted_dialogue


class MistralChatTemplate(PromptTemplate):
    """
    Formats according to `Mistral's instruct model <https://docs.mistral.ai/models/>`_.

    It is identical to `Llama2ChatTemplate`, except it does not support system
    prompts.

    Example:
        .. code-block:: text

            "[INST] I am going to Paris, what should I see? [/INST] Paris, the capital
            of France, is known for its stunning architecture..."

    """

    B_INST, E_INST = "[INST]", "[/INST]"
    system = None
    user = f"{B_INST} {{content}} {E_INST} "
    assistant = ""

    @classmethod
    def format(
        cls,
        sample: List[Message],
    ) -> List[Message]:
        """
        Format user messages with appropriate tags.

        Args:
            sample (List[Message]): a single conversation, structured as a list
                of :class:`~torchtune.data.Message` objects

        Returns:
            The formatted list of messages

        Raises:
            ValueError: If system prompts are provided
        """
        formatted_dialogue = []
        for message in sample:
            content = ""
            if message.role == "system":
                raise ValueError(
                    "System prompts are not supported in MistralChatTemplate"
                )
            elif message.role == "user":
                content = cls.user.format(
                    content=message.content,
                )
            elif message.role == "assistant":
                # No special formatting needed for assistant message
                content = message.content
            formatted_dialogue.append(
                Message(role=message.role, content=content, masked=message.masked),
            )
        return formatted_dialogue


class ChatMLTemplate(PromptTemplate):
    """
    OpenAI's `Chat Markup Language
    <https://github.com/MicrosoftDocs/azure-docs/blob/772c14eeabfa0c0c561d5c2d34ef19341f528b7b/articles/ai-services/openai/how-to/chat-markup-language.md>`_
    used by their chat models.

    It is the default chat template used by HuggingFace models.

    Example:
        .. code-block:: text

            <|im_start|>system
            Provide some context and/or instructions to the model.<|im_end|>
            <|im_start|>user
            The user’s message goes here<|im_end|>
            <|im_start|>assistant
            The assistant’s response goes here<|im_end|>
    """

    IM_START, IM_END = "<|im_start|>", "<|im_end|>"
    system = f"{IM_START}system\n{{content}}{IM_END}\n"
    user = f"{IM_START}user\n{{content}}{IM_END}\n"
    assistant = f"{IM_START}assistant\n{{content}}{IM_END}"

    @classmethod
    def format(
        cls,
        sample: List[Message],
    ) -> List[Message]:
        """
        Format user and system messages with appropriate tags.

        Args:
            sample (List[Message]): a single conversation, structured as a list
                of `Message` objects

        Returns:
            The formatted list of messages
        """
        formatted_dialogue = []
        for message in sample:
            content = ""
            if message.role == "system":
                content = cls.system.format(content=message.content)
            elif message.role == "user":
                content = cls.user.format(
                    content=message.content,
                )
            elif message.role == "assistant":
                content = cls.assistant.format(
                    content=message.content,
                )
            formatted_dialogue.append(
                Message(role=message.role, content=content, masked=message.masked),
            )
        return formatted_dialogue

class AlpacaInstructTemplate(PromptTemplate):
    """
    Prompt template for Alpaca-style datasets. Template prompt changes slightly depending
    on if there's an instruction + input or just an instruction.
    """

    template = {
        "prompt_input": (
            "Below is an instruction that describes a task, paired with an input that provides further context. "
            "Write a response that appropriately completes the request.\n\n"
            "### Instruction:\n{instruction}\n\n### Input:\n{input}\n\n### Response:\n"
        ),
        "prompt_no_input": (
            "Below is an instruction that describes a task. "
            "Write a response that appropriately completes the request.\n\n"
            "### Instruction:\n{instruction}\n\n### Response:\n"
        ),
    }

    @classmethod
    def format(
        cls, sample: Mapping[str, Any], column_map: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate prompt from instruction and input.

        Args:
            sample (Mapping[str, Any]): a single data sample with instruction
            column_map (Optional[Dict[str, str]]): a mapping from the expected
                placeholder names in the template to the column names in the sample.
                If None, assume these are identical.

        Returns:
            The formatted prompt
        """
        column_map = column_map or {}
        key_input = column_map.get("input", "input")
        key_instruction = column_map.get("instruction", "instruction")

        if key_input in sample and sample[key_input]:
            prompt = cls.template["prompt_input"].format(
                instruction=sample[key_instruction], input=sample[key_input]
            )
        else:
            prompt = cls.template["prompt_no_input"].format(
                instruction=sample[key_instruction]
            )
        return prompt


class GrammarErrorCorrectionTemplate(PromptTemplate):
    """
    Prompt template for grammar correction datasets.
    """

    template = "Correct this to standard English: {sentence}\n---\nCorrected: "

    @classmethod
    def format(
        cls, sample: Mapping[str, Any], column_map: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate prompt from sentence.

        Args:
            sample (Mapping[str, Any]): a single data sample with sentence
            column_map (Optional[Dict[str, str]]): a mapping from the expected
                placeholder names in the template to the column names in the sample.
                If None, assume these are identical.

        Returns:
            The formatted prompt
        """
        column_map = column_map or {}
        key_sentence = column_map.get("sentence", "sentence")

        prompt = cls.template.format(sentence=sample[key_sentence])
        return prompt


class SummarizeTemplate(PromptTemplate):
    """
    Prompt template to format datasets for summarization tasks.
    """

    template = "Summarize this dialogue:\n{dialogue}\n---\nSummary:\n"

    @classmethod
    def format(
        cls, sample: Mapping[str, Any], column_map: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate prompt from dialogue.

        Args:
            sample (Mapping[str, Any]): a single data sample with dialog
            column_map (Optional[Dict[str, str]]): a mapping from the expected
                placeholder names in the template to the column names in the sample.
                If None, assume these are identical.

        Returns:
            The formatted prompt
        """
        column_map = column_map or {}
        key_dialogue = column_map.get("dialogue", "dialogue")

        prompt = cls.template.format(dialogue=sample[key_dialogue])
        return prompt


class StackExchangedPairedTemplate(PromptTemplate):
    """
    Prompt template for preference datasets similar to StackExchangedPaired.
    """

    template = "Question: {question}\n\nAnswer: "

    @classmethod
    def format(
        cls, sample: Mapping[str, Any], column_map: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Generate prompt from instruction and input.

        Args:
            sample (Mapping[str, Any]): a single data sample with instruction
            column_map (Optional[Dict[str, str]]): a mapping from the expected
                placeholder names in the template to the column names in the sample.
                If None, assume these are identical.

        Returns:
            The formatted prompt
        """
        column_map = column_map or {}
        key_prompt = column_map.get("prompt", "prompt")
        prompt = cls.template.format(question=sample[key_prompt])

        return prompt