# Wavelength windows in Explore

The nine rows are approximate wavelength selections, not the six physical
detectors and not maps of detected chemical abundance. An exposure is assigned
using its measured wavelength at the area's centre. Wavelength varies across
each detector image, so this is also an approximation across a wide field.

Detector coverage, in micrometres: D1 0.75–1.09; D2 1.10–1.62;
D3 1.63–2.41; D4 2.42–3.82; D5 3.83–4.41; D6 4.42–5.00.
The current feature windows extend ±4% around their listed central wavelengths;
these are browsing windows, not matched line filters or continuum-subtracted
measurements. Starlight uses 0.75–1.30 and the long-wavelength row uses 3.8–5.0.

Hydrogen and helium associations describe possible spectral features. Ice and
methane absorption generally require comparison with surrounding continuum.
Light near 3.3 µm may contain PAH emission, methane absorption, and continuum.
Broad 4–5 µm brightness is not uniquely thermal emission or a temperature map.
Neither a tinted image nor selecting a row establishes a chemical detection.

Each row shows `matching observations / available observations`: the numerator
uses the active band combination and selected timeline range, and the denominator
uses every observation with that row's wavelength coverage in the returned area
sample. These are observation counts, not detector counts, download progress,
or totals over the entire archive. The backend currently samples up to 18
observation IDs; the denominator must not be presented as an archive-wide total.

Official references:

- [IRSA: spectral images, detector ranges and wavelength WCS](https://caltech-ipac.github.io/irsa-tutorials/spherex-intro/)
- [SPHEREx: ice absorption spectroscopy](https://spherex.caltech.edu/page/the-origin-of-water-in-planetary-systems)
- [NASA: SPHEREx brown-dwarf molecular absorption](https://www.nasa.gov/missions/spherex/nasas-spherex-telescope-sees-menagerie-of-brown-dwarfs/)
- [NASA: SPHEREx ice and PAH spectral maps](https://science.nasa.gov/astrophysics/programs/cosmic-origins/community/ir-stig-seminar-series-4-may-2026/)
