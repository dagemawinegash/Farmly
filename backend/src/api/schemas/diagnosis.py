from pydantic import BaseModel


class SimilarImage(BaseModel):
    url: str | None = None
    citation: str | None = None


class CropCandidate(BaseModel):
    name: str | None = None
    scientific_name: str | None = None
    probability: float | None = None
    similar_images: list[SimilarImage] = []


class DiseaseCandidate(BaseModel):
    name: str | None = None
    scientific_name: str | None = None
    probability: float | None = None
    similar_images: list[SimilarImage] = []


class DiagnosisResponse(BaseModel):
    is_plant: bool
    top_crop: CropCandidate | None = None
    top_disease: DiseaseCandidate | None = None
    crops: list[CropCandidate]
    diseases: list[DiseaseCandidate]
    advice_text: str
    used_fallback: bool

