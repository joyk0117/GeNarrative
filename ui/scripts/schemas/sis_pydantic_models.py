from __future__ import annotations

"""SIS Pydantic schema definitions (Pydantic v2, for Ollama structured output).

- The schema is based on docs/SIS_pydantic_schema.md.
- The main structured-output targets are:
  - StorySemantics
  - SceneSemantics
  - MediaSemantics

Notes:
- We keep the models small and purely declarative.
- List fields use default_factory to avoid shared mutable defaults.
"""

from typing import List, Literal, Optional

from pydantic import BaseModel, Field


# ----------------------------
# Common policies (reused)
# ----------------------------


class TextPolicy(BaseModel):
    """Text policy reused by Story/Scene/Media."""

    style: Optional[str] = None
    language: Optional[str] = None
    tone: Optional[str] = None
    point_of_view: Optional[str] = None


class VisualPolicy(BaseModel):
    """Visual policy reused by Story/Scene/Media."""

    style: Optional[str] = None
    composition: Optional[str] = None
    lighting: Optional[str] = None
    perspective: Optional[str] = None


class AudioPolicy(BaseModel):
    """Audio policy reused by Story/Scene/Media."""

    genre: Optional[str] = None
    tempo: Optional[str] = None
    instruments: List[str] = Field(default_factory=list)
    mood: Optional[str] = None


# ----------------------------
# Common semantics (reused)
# ----------------------------


class CharacterVisual(BaseModel):
    """Additional visual details for a character."""

    hair: Optional[str] = None
    clothes: Optional[str] = None


class Character(BaseModel):
    """Character definition reused by Story/Scene/Media."""

    name: Optional[str] = None
    traits: List[str] = Field(default_factory=list)
    visual: Optional[CharacterVisual] = None


class SISObject(BaseModel):
    """Salient motif/object and its representative colors."""

    name: Optional[str] = None
    colors: List[str] = Field(default_factory=list)


class CommonSemanticsBase(BaseModel):
    """Common semantics used by SceneSemantics/MediaSemantics."""

    mood: Optional[str] = None
    descriptions: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    time: Optional[str] = None
    weather: Optional[str] = None
    characters: List[Character] = Field(default_factory=list)
    objects: List[SISObject] = Field(default_factory=list)


# ----------------------------
# Story SIS
# ----------------------------


class StorySIS(BaseModel):
    """SIS object for a whole story (for reference/use in app)."""

    sis_type: Literal["story"] = "story"
    story_id: Optional[str] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    story_type: Optional[str] = None
    semantics: StorySemantics


class StoryCommonSemantics(BaseModel):
    """Common semantics for a story (semantics.common)."""

    themes: List[str] = Field(default_factory=list)
    descriptions: List[str] = Field(default_factory=list)


class StorySemantics(BaseModel):
    """StorySIS.semantics (structured output target)."""

    common: StoryCommonSemantics
    text: Optional[TextPolicy] = None
    visual: Optional[VisualPolicy] = None
    audio: Optional[AudioPolicy] = None


# ----------------------------
# Scene SIS
# ----------------------------


class SceneSIS(BaseModel):
    """SIS object for a single scene (for reference/use in app)."""

    sis_type: Literal["scene"] = "scene"
    scene_id: Optional[str] = None
    summary: Optional[str] = None
    semantics: SceneSemantics


class SceneSemantics(BaseModel):
    """SceneSIS.semantics (structured output target)."""

    common: CommonSemanticsBase
    text: Optional[TextPolicy] = None
    visual: Optional[VisualPolicy] = None
    audio: Optional[AudioPolicy] = None


# ----------------------------
# Media SIS
# ----------------------------


class MediaSIS(BaseModel):
    """SIS object for a media unit (for reference/use in app)."""

    sis_type: Literal["media"] = "media"
    media_id: Optional[str] = None
    summary: Optional[str] = None
    media_type: Optional[str] = None
    semantics: MediaSemantics
    provenance: Optional[Provenance] = None


class MediaSemantics(BaseModel):
    """MediaSIS.semantics (structured output target)."""

    common: CommonSemanticsBase
    text: Optional[TextPolicy] = None
    visual: Optional[VisualPolicy] = None
    audio: Optional[AudioPolicy] = None


class ProvenanceAsset(BaseModel):
    """Input asset used to create the media."""

    asset_id: Optional[str] = None
    uri: Optional[str] = None


class ProvenanceGenerator(BaseModel):
    """Generator metadata (system/model, etc.)."""

    system: Optional[str] = None
    model: Optional[str] = None


class Provenance(BaseModel):
    """Provenance container."""

    assets: List[ProvenanceAsset] = Field(default_factory=list)
    generator: Optional[ProvenanceGenerator] = None


# Ensure forward references are resolved (Pydantic v2).
StorySIS.model_rebuild()
SceneSIS.model_rebuild()
MediaSIS.model_rebuild()
