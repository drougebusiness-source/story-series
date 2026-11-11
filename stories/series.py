"""One story series on disk: <slug>/series.yaml (settings), BRAND.md and SEASON1.md (the bible), CANON.md (what has
happened, appended after every episode) and state.json (episodes, votes, Instagram ids)."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SLUGS = ("compliant", "last-draft", "roll-for-fate", "driftborn")
FONTS = ROOT / "assets" / "fonts"


@dataclass
class Series:
    slug: str
    cfg: dict = field(default_factory=dict)

    @classmethod
    def load(cls, slug: str) -> "Series":
        if slug not in SLUGS:
            raise SystemExit(f"unknown series {slug!r}; pick one of {', '.join(SLUGS)}")
        return cls(slug, yaml.safe_load((ROOT / slug / "series.yaml").read_text(encoding="utf-8")))

    @classmethod
    def for_slot(cls, hour_utc: str) -> "Series | None":
        for s in SLUGS:
            se = cls.load(s)
            if str(se.cfg.get("slot_utc")) == hour_utc:
                return se
        return None

    # -- files
    @property
    def dir(self) -> Path:
        return ROOT / self.slug

    def text(self, name: str) -> str:
        p = self.dir / name
        return p.read_text(encoding="utf-8") if p.exists() else ""

    @property
    def state(self) -> dict:
        return json.loads(self.text("state.json") or '{"episodes": []}')

    def save_state(self, state: dict) -> None:
        tmp = self.dir / "state.json.tmp"
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        tmp.replace(self.dir / "state.json")

    def add_canon(self, line: str) -> None:
        with open(self.dir / "CANON.md", "a", encoding="utf-8") as f:
            f.write(line.rstrip() + "\n")

    # -- settings
    @property
    def title(self) -> str:
        return self.cfg["title"]

    @property
    def live(self) -> bool:
        return bool(self.cfg.get("live"))

    def font(self, kind: str) -> Path:
        return FONTS / self.cfg["font_head" if kind == "head" else "font_body"]

    def color(self, name: str) -> str:
        return self.cfg["colors"][name]

    # -- Instagram credentials (GitHub secrets, one pair per account)
    @property
    def ig_env(self) -> tuple[str, str]:
        s = self.cfg["secret"]
        return f"IG_USER_ID_{s}", f"META_PAGE_TOKEN_{s}"

    def ig_creds(self) -> tuple[str, str] | None:
        uid, tok = (os.environ.get(k, "") for k in self.ig_env)
        return (uid, tok) if uid and tok else None
