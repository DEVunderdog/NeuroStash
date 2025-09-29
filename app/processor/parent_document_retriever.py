import enum
import logging
import copy
import numpy as np
from langchain_experimental.text_splitter import (
    combine_sentences,
    calculate_cosine_distances,
)
from langchain_core.embeddings import Embeddings
from langchain_core.documents import Document
from app.processor.splitters import SentenceSplitter
from typing import List, Tuple, cast, Optional, Iterable, Sequence

logger = logging.getLogger(__name__)


class BreakPointThresholdTypeEnum(enum.Enum):
    PERCENTILE = "percentile"
    STANDARD_DEVIATION = "standard_deviation"
    INTERQUARTILE = "interquartile"
    GRADIENT = "gradient"


class ParentDocumentRetriever:
    def __init__(
        self,
        embeddings: Embeddings,
    ):
        self.sentence_splitters = SentenceSplitter()
        self.embeddings = embeddings
        self.parent_buffer_size = 3
        self.child_buffer_size = 1
        self.parent_breakpoint_threshold_type = (
            BreakPointThresholdTypeEnum.INTERQUARTILE
        )
        self.child_breakpoint_threshold_type = BreakPointThresholdTypeEnum.PERCENTILE
        self.parent_breakpoint_threshold: float = 1.5
        self.child_breakpoint_threshold: float = 85.0

    def _calculate_breakpoint_threshold(
        self,
        distances: List[float],
        breakpoint_threshold_type: BreakPointThresholdTypeEnum,
        breakpoint_threshold_amount: float,
    ) -> Tuple[float, List[float]]:
        if breakpoint_threshold_type == BreakPointThresholdTypeEnum.PERCENTILE:
            return (
                cast(
                    float,
                    np.percentile(distances, breakpoint_threshold_amount),
                ),
                distances,
            )
        elif (
            breakpoint_threshold_type == BreakPointThresholdTypeEnum.STANDARD_DEVIATION
        ):
            return (
                cast(
                    float,
                    np.mean(distances)
                    + breakpoint_threshold_amount * np.std(distances),
                ),
                distances,
            )
        elif breakpoint_threshold_type == BreakPointThresholdTypeEnum.INTERQUARTILE:
            q1, q3 = np.percentile(distances, [25, 75])
            iqr = q3 - q1

            return (
                q3 + breakpoint_threshold_amount * iqr,
                distances,
            )
        elif breakpoint_threshold_type == BreakPointThresholdTypeEnum.GRADIENT:
            distance_gradient = np.gradient(distances, range(0, len(distances)))
            return (
                cast(
                    float,
                    np.percentile(distance_gradient, breakpoint_threshold_amount),
                ),
                distance_gradient,
            )
        else:
            raise ValueError(
                f"Got unexpected `breakpoint_threshold_type`: "
                f"{self.breakpoint_threshold_type}"
            )

    def _calculate_sentence_distances(
        self,
        single_sentences_list: List[str],
        buffer_size: int,
    ) -> Tuple[List[float], List[dict]]:
        _sentences = [
            {"sentence": x, "index": i} for i, x in enumerate(single_sentences_list)
        ]
        sentences = combine_sentences(_sentences, buffer_size)
        embeddings = self.embeddings.embed_documents(
            [x["combined_sentence"] for x in sentences]
        )
        for i, sentence in enumerate(sentences):
            sentence["combined_sentence_embedding"] = embeddings[i]

        return calculate_cosine_distances(sentences)

    def _split_text(
        self,
        text: str,
        breakpoint_threshold_type: BreakPointThresholdTypeEnum,
        breakpoint_threshold_amount: int,
        buffer_size: int,
    ) -> List[str]:
        single_sentences_list = self.sentence_splitters.split_text(text=text)

        if len(single_sentences_list) == 1:
            return single_sentences_list

        distances, sentences = self._calculate_sentence_distances(
            single_sentences_list=single_sentences_list, buffer_size=buffer_size
        )

        breakpoint_distance_threshold, breakpoint_array = (
            self._calculate_breakpoint_threshold(
                distances=distances,
                breakpoint_threshold_type=breakpoint_threshold_type,
                breakpoint_threshold_amount=breakpoint_threshold_amount,
            )
        )

        indices_above_thresh = [
            i
            for i, x in enumerate(breakpoint_array)
            if x > breakpoint_distance_threshold
        ]

        chunks = []
        start_index = 0

        for index in indices_above_thresh:
            end_index = index

            group = sentences[start_index : end_index + 1]
            combined_text = " ".join([d["sentence"] for d in group])
            chunks.append(combined_text)
            start_index = index + 1

        if start_index < len(sentences):
            combined_text = " ".join([d["sentence"] for d in sentences[start_index:]])
            chunks.append(combined_text)
        return chunks

    def _create_documents(
        self,
        child_documents: bool,
        texts: List[str],
        metadatas: Optional[List[dict]] = None,
    ) -> List[Document]:
        _metadatas = metadatas or [{}] * len(texts)
        documents = []
        breakpoint_threshold_type = self.parent_breakpoint_threshold_type
        breakpoint_threshold_amount = self.parent_breakpoint_threshold
        buffer_size = self.parent_buffer_size
        if child_documents:
            breakpoint_threshold_type = self.child_breakpoint_threshold_type
            breakpoint_threshold_amount = self.child_breakpoint_threshold
            buffer_size = self.child_buffer_size

        for i, text in enumerate(texts):
            for chunk in self._split_text(
                text=text,
                breakpoint_threshold_type=breakpoint_threshold_type,
                breakpoint_threshold_amount=breakpoint_threshold_amount,
                buffer_size=buffer_size,
            ):
                metadata = copy.deepcopy(_metadatas[i])
                new_doc = Document(page_content=chunk, metadata=metadata)
                documents.append(new_doc)

        return documents

    def _split_documents(self, documents: Iterable[Document]) -> List[dict]:

        splitted_data: List[dict] = []

        texts, metadatas = [], []
        for doc in documents:
            texts.append(doc.page_content)
            metadatas.append(doc.metadata)

        parent_chunked_docs = self._create_documents(
            child_documents=False, texts=texts, metadatas=metadatas
        )

        logger.info(f"length of parent chunked docs: {len(parent_chunked_docs)}")

        if len(parent_chunked_docs) != 0:
            for doc in parent_chunked_docs:
                text = [doc.page_content]
                child_chunked_doc = self._create_documents(
                    child_documents=True,
                    texts=text,
                )
                data = {"parent_doc": doc, "child_doc": child_chunked_doc}
                splitted_data.append(data)

        return splitted_data

    def transform_documents(self, documents: Sequence[Document]) -> List[dict]:
        return self._split_documents(list(documents))
