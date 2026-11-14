from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, model_validator


class SkyRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False, extra="forbid")
    source: Literal["local", "remote"] = "local"
    ra: float = Field(ge=0, lt=360, description="ICRS RA in degrees")
    dec: float = Field(ge=-90, le=90, description="ICRS Dec in degrees")
    detector: int = Field(default=1, ge=1, le=6)
    collections: list[Literal["spherex_dr1", "spherex_qr3", "spherex_dr1_deep", "spherex_qr3_deep"]] = Field(default=["spherex_dr1", "spherex_qr3"], min_length=1, max_length=4)
    mjd_start: float | None = None
    mjd_end: float | None = None
    limit: int = Field(default=12, ge=1, le=24)

    @model_validator(mode="after")
    def dates(self):
        if self.mjd_start is not None and self.mjd_end is not None and self.mjd_start > self.mjd_end:
            raise ValueError("mjd_start must be <= mjd_end")
        self.collections = list(dict.fromkeys(self.collections))
        return self


class TimelapseRequest(SkyRequest):
    size_px: int = Field(default=96, ge=16, le=256)
    pixel_scale_arcsec: float = Field(default=6.15, ge=6.15, le=12.3)
    subtract_background: bool = True
    # SOURCE (bit 21) identifies known sources, not defective pixels.
    bad_bits: int = Field(default=0xFFFFFFFF ^ (1 << 21), ge=0, le=0xFFFFFFFF)


class Exposure(BaseModel):
    id: str
    collection: str
    detector: int
    mjd: float
    fits_url: str
    local_cutout_url: str | None = None


class SearchResult(BaseModel):
    exposures: list[Exposure]
    truncated: bool
    warnings: list[str] = []
    source: Literal["local", "remote"] = "remote"
