from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Dict, Iterable, List, Tuple


_WORD_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)


def _strip_accents(text: str) -> str:
    if not text:
        return ""
    t = unicodedata.normalize("NFKD", text)
    t = "".join(ch for ch in t if not unicodedata.combining(ch))
    return t


def normalize(text: str) -> str:
    return " ".join(_strip_accents((text or "")).lower().split())


def tokenize(text: str) -> List[str]:
    return [t for t in _WORD_RE.findall(_strip_accents(text).lower()) if t]


@dataclass(frozen=True)
class Lexicon:
    pos: Dict[str, float]
    neg: Dict[str, float]
    negators: Tuple[str, ...]
    intensifiers: Dict[str, float]
    diminishers: Dict[str, float]

    @staticmethod
    def small_pt() -> "Lexicon":
        # Pequeno léxico inicial (ajustável). Valores ~força.
        pos = {
            "bom": 1.0,
            "boa": 1.0,
            "otimo": 1.5,
            "otima": 1.5,
            "excelente": 2.0,
            "parabens": 1.5,
            "apoiar": 1.0,
            "apoio": 1.0,
            "competente": 1.5,
            "honesto": 1.5,
            "lideranca": 1.0,
            "vitoria": 1.2,
            "acertou": 1.2,
            "certo": 0.8,
            "tranquilo": 0.8,
            "feliz": 1.2,
        }
        neg = {
            "ruim": -1.2,
            "pessimo": -2.0,
            "horrivel": -2.2,
            "vergonha": -1.8,
            "vergonhoso": -1.8,
            "corrupto": -2.5,
            "mentiroso": -2.0,
            "incompetente": -2.0,
            "fracasso": -1.8,
            "crime": -1.5,
            "criminoso": -2.2,
            "canalha": -2.2,
            "lixo": -2.0,
            "odeio": -2.0,
            "enganou": -1.5,
            "errado": -1.2,
            "culpa": -1.0,
            "golpe": -1.5,
            "vagabundo": -2.5,
            "seboso": -1.6,
        }
        negators = ("nao", "nunca", "jamais", "sem")
        intensifiers = {
            "muito": 1.5,
            "mais": 1.2,
            "super": 1.6,
            "extremamente": 1.8,
            "bastante": 1.3,
        }
        diminishers = {
            "pouco": 0.6,
            "meio": 0.7,
            "quase": 0.7,
        }
        return Lexicon(pos=pos, neg=neg, negators=negators, intensifiers=intensifiers, diminishers=diminishers)


@dataclass
class SentimentResult:
    label: str  # "positivo" | "negativo" | "neutro"
    score: float  # signed sentiment [-inf, +inf] (avg over hits)
    confidence: float  # [0,1]
    hits: int  # quantidade de termos polarizados considerados
    mentioned: bool  # alvo mencionado no texto


class TargetedLexiconAnalyzer:
    def __init__(self, lex: Lexicon | None = None):
        self.lex = lex or Lexicon.small_pt()

    def _term_polarity(self, term: str) -> float:
        if term in self.lex.pos:
            return self.lex.pos[term]
        if term in self.lex.neg:
            return self.lex.neg[term]
        return 0.0

    def analyze(self, text: str, target_names: Iterable[str] | None = None) -> SentimentResult:
        toks = tokenize(text)
        if not toks:
            return SentimentResult(label="neutro", score=0.0, confidence=0.2, hits=0, mentioned=False)

        # Alvo mencionado? (nome completo, sobrenome)
        mentioned = False
        if target_names:
            norm_targets = [normalize(n) for n in target_names if n]
            flat = " ".join(toks)
            for nt in norm_targets:
                if not nt:
                    continue
                parts = [p for p in nt.split(" ") if p]
                # nome completo
                if nt in flat:
                    mentioned = True
                    break
                # sobrenome
                if any(p in toks for p in parts[-1:]):
                    mentioned = True
                    break

        score_sum = 0.0
        hits = 0
        window = 3  # janela de negação
        for i, t in enumerate(toks):
            pol = self._term_polarity(t)
            if pol == 0.0:
                continue

            # Intensificadores e atenuadores na vizinhança imediata
            mult = 1.0
            prev = toks[i - 1] if i - 1 >= 0 else ""
            if prev in self.lex.intensifiers:
                mult *= self.lex.intensifiers[prev]
            if prev in self.lex.diminishers:
                mult *= self.lex.diminishers[prev]

            # Negação: se houver negador em até N tokens antes, inverte
            j = i - 1
            negated = False
            steps = 0
            while j >= 0 and steps < window:
                if toks[j] in self.lex.negators:
                    negated = True
                    break
                # Quebra simples em conectivos que encerram escopo
                if toks[j] in ("mas", "porem", "porém", "so", "só"):
                    break
                j -= 1
                steps += 1

            if negated:
                pol *= -1

            score_sum += pol * mult
            hits += 1

        if hits == 0:
            return SentimentResult(label="neutro", score=0.0, confidence=0.3 + (0.2 if mentioned else 0.0), hits=0, mentioned=mentioned)

        avg = score_sum / hits
        # Thresholds simples; ajustar por validação
        if avg > 0.2:
            label = "positivo"
        elif avg < -0.2:
            label = "negativo"
        else:
            label = "neutro"

        # Confiança: cresce com |avg|, com bônus se o alvo foi mencionado
        conf = min(1.0, 0.5 + min(0.5, abs(avg)))
        if mentioned:
            conf = min(1.0, conf + 0.15)

        return SentimentResult(label=label, score=round(avg, 4), confidence=round(conf, 3), hits=hits, mentioned=mentioned)


