"""Lab 18 — trie. Reference solution."""
from __future__ import annotations

from typing import Dict, List, Set


class Trie:
    def __init__(self) -> None:
        self.root: Dict = {"#": False}          # "#": terminal marker

    def insert(self, word: str) -> None:
        node = self.root
        for ch in word:
            if ch not in node:
                node[ch] = {"#": False}
            node = node[ch]
        node["#"] = True

    def _walk(self, s: str):
        node = self.root
        for ch in s:
            if ch not in node:
                return None
            node = node[ch]
        return node

    def search(self, word: str) -> bool:
        node = self._walk(word)
        return node is not None and node["#"] is True

    def starts_with(self, prefix: str) -> bool:
        return self._walk(prefix) is not None


class WordDictionary:
    def __init__(self) -> None:
        self.trie = Trie()

    def add_word(self, word: str) -> None:
        self.trie.insert(word)

    def search(self, word: str) -> bool:
        def dfs(node, i: int) -> bool:
            if i == len(word):
                return node["#"] is True
            ch = word[i]
            if ch == ".":
                for key, child in node.items():
                    if key != "#" and dfs(child, i + 1):
                        return True
                return False
            if ch not in node:
                return False
            return dfs(node[ch], i + 1)

        return dfs(self.trie.root, 0)


def autocomplete(trie: Trie, prefix: str, k: int) -> List[str]:
    node = trie._walk(prefix)
    if node is None or k <= 0:
        return []
    out: List[str] = []

    def dfs(node, acc: str) -> bool:
        if node["#"]:
            out.append(prefix + acc)
            if len(out) >= k:
                return True
        for ch in sorted(k for k in node if k != "#"):
            if dfs(node[ch], acc + ch):
                return True
        return False

    dfs(node, "")
    return out[:k]


def find_words(board: List[List[str]], words: List[str]) -> List[str]:
    if not board or not board[0]:
        return []
    trie = Trie()
    for w in words:
        if w:
            trie.insert(w)
    rows, cols = len(board), len(board[0])
    found: Set[str] = set()

    def dfs(r: int, c: int, node, path: str) -> None:
        if "#" in node and node["#"]:
            found.add(path)
        if r < 0 or r >= rows or c < 0 or c >= cols:
            return
        ch = board[r][c]
        if ch == "#" or ch not in node:
            return
        nxt = node[ch]
        board[r][c] = "#"
        dfs(r + 1, c, nxt, path + ch)
        dfs(r - 1, c, nxt, path + ch)
        dfs(r, c + 1, nxt, path + ch)
        dfs(r, c - 1, nxt, path + ch)
        board[r][c] = ch

    for r in range(rows):
        for c in range(cols):
            dfs(r, c, trie.root, "")
            if len(found) == len(set(w for w in words if w)):
                break
    return list(found)


def longest_common_prefix_via_trie(words: List[str]) -> str:
    if not words:
        return ""
    if len(words) == 1:
        return words[0]
    trie = Trie()
    for w in words:
        trie.insert(w)
    node = trie.root
    prefix_chars: List[str] = []
    while True:
        if node["#"]:
            break                                # a word ends here → fork point
        children = [k for k in node if k != "#"]
        if len(children) != 1:
            break
        ch = children[0]
        prefix_chars.append(ch)
        node = node[ch]
    return "".join(prefix_chars)
