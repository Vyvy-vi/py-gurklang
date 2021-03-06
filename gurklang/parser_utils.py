from dataclasses import dataclass
import re
from dataclasses import dataclass
from typing import Callable, Collection, Generic, Iterable, Iterator, List, Optional, Pattern, TypeVar, Dict, Tuple, Type, Union
from collections import deque


TokenName = TypeVar("TokenName", bound=str)
IgnoredToken = TypeVar("IgnoredToken", bound=str)


@dataclass(frozen=True)
class Token(Generic[TokenName]):
    name: TokenName
    value: str
    position: int

    @property
    def span(self) -> Tuple[int, int]:
        return (self.position, self.position + len(self.value))


class TokenStream(Generic[TokenName]):
    def __init__(self, it: Iterator[Token[TokenName]]):
        self.it = it
        self._last_token: Optional[Token[TokenName]] = None
        self._extra_tokens: "deque[Token[TokenName]]" = deque()

    @property
    def last_token(self) -> Token[TokenName]:
        if self._last_token is None:
            raise ValueError("No tokens yet")
        return self._last_token

    def push(self, token: Token[TokenName]):
        self._extra_tokens.appendleft(token)

    def __iter__(self):
        return self

    def __next__(self):
        try:
            token = next(self.it)
        except StopIteration:
            if not self._extra_tokens:
                raise
            token = self._extra_tokens.pop()
        self._last_token = token
        return token


@dataclass
class Tokenizer(Generic[TokenName, IgnoredToken]):
    """
    Tokenizer with enhanced type safety.

    Don't instantiate this class directly, use `build_tokenizer` instead.
    """
    pattern: Pattern[str]
    ignore: Collection[IgnoredToken] = ()
    middleware: Callable[[TokenName, str], Tuple[TokenName, str]] = lambda name, v: (name, v)

    @property
    def token_type(self) -> Type[Token[TokenName]]:
        return Token

    @property
    def token_stream_type(self) -> Type[TokenStream[TokenName]]:
        return TokenStream

    @property
    def token_name_type(self) -> Type[TokenName]:
        return str  # type: ignore

    def _tokenize_gen(self, source: str) -> Iterator[Token[TokenName]]:
        for t in self._tokenize_all(source):
            if t.name not in self.ignore:
                yield t  # type: ignore

    def _tokenize_all(self, source: str) -> Iterator[Token[Union[TokenName, IgnoredToken]]]:
        for match in self.pattern.finditer(source):
            name, value = next(
                (name, value) for (name, value) in match.groupdict().items()
                if value is not None
            )
            name, value = self.middleware(name, value)
            yield Token(name, value, match.start())  # type: ignore

    def tokenize(self, source: str) -> TokenStream[TokenName]:
        return TokenStream(self._tokenize_gen(source))

    def tokenize_with_ignored(self, source: str) -> TokenStream[Union[TokenName, IgnoredToken]]:
        return TokenStream(self._tokenize_all(source))


def build_regexp_source(lookup: Iterable[Tuple[str, str]]):
    return "|".join(f"(?P<{name}>{pattern})" for name, pattern in lookup)  # type:ignore


def build_regexp(lookup: Iterable[Tuple[str, str]], flags: re.RegexFlag = re.RegexFlag(0)):
    return re.compile(build_regexp_source(lookup), flags)


def _make_middleware(lookup: Dict[TokenName, Callable[[str], Tuple[TokenName, str]]]):
    def middleware(name: TokenName, value: str):
        if name in lookup:
            return lookup[name](value)
        else:
            return (name, value)
    return middleware


def build_tokenizer(
    normal_tokens: Tuple[Tuple[TokenName, Optional[str]], ...],
    flags: re.RegexFlag = re.RegexFlag(0),
    *,
    ignored_tokens: Tuple[Tuple[IgnoredToken, str], ...] = (),
    middleware: Dict[TokenName, Callable[[str], Tuple[TokenName, str]]] = {},
) -> Tokenizer[TokenName, IgnoredToken]:
    return Tokenizer(
        build_regexp(tuple(filter(None, normal_tokens)) + ignored_tokens, flags),
        ignore=[name for name, _pattern in ignored_tokens],
        middleware=_make_middleware(middleware)
    ) # type: ignore
