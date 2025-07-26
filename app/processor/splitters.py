import logging
import spacy
from langchain.text_splitter import TextSplitter
from app.constants.models import (
    SPACY_MODEL,
    SPACY_PARSER,
    SPACY_TAGGER,
    SPACY_LEM,
    SPACY_NER,
    SPACY_SENTENCIZER,
)
from typing import List

logger = logging.getLogger(__name__)


class SentenceSplitter(TextSplitter):
    def __init__(self):
        super().__init__()
        self.nlp = spacy.load(
            SPACY_MODEL, exclude=[SPACY_PARSER, SPACY_TAGGER, SPACY_LEM, SPACY_NER]
        )
        self.nlp.add_pipe(SPACY_SENTENCIZER)

    def split_text(self, text) -> List[str]:
        doc = self.nlp(text=text)
        return [sent.text.strip() for sent in doc.sents]
