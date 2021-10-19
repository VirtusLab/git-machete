from typing import Optional


class AnyBranch(str):
    @staticmethod
    def of(value: str) -> Optional["AnyBranch"]:
        return AnyBranch(value) if value else None


class LocalBranch(AnyBranch):
    @staticmethod
    def of(value: str) -> Optional["LocalBranch"]:
        return LocalBranch(value) if value else None


class RemoteBranch(AnyBranch):
    @staticmethod
    def of(value: str) -> Optional["RemoteBranch"]:
        return RemoteBranch(value) if value else None


class Commit(str):
    @staticmethod
    def of(value: str) -> Optional["Commit"]:
        return Commit(value) if value else None
