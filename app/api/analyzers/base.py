from abc import ABC, abstractmethod

from analyzers.file_index import FileIndex
from graph.models import GraphFactPatch


class Analyzer(ABC):
    def name(self) -> str:
        return self.__class__.__name__

    @abstractmethod
    def supports(self, file_index: FileIndex) -> bool:
        pass

    @abstractmethod
    def analyze(self, file_index: FileIndex) -> GraphFactPatch:
        pass
