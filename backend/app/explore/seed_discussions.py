"""Create labelled demo discussions using cached SPHEREx observations."""
import asyncio
from datetime import datetime, timezone
import json

from .community import database, existing, Region
from .common import SHOTS, key, mjd_to_iso
from .finding_media import attach_media, visible_reference
from .sources import ensure_shots
from .warm_demo import configure_index, recommended_targets

EXAMPLES = {
    'barnard': ('sample-barnard-motion', 'Checking motion near Barnard’s Star', 'Dr. Maya Rao',
        'I want to compare the infrared revisits around Barnard’s Star using a consistent patch of sky. The wide view keeps neighbouring sources in the frame, giving us reference points when we compare dates.\n\nThe attached blink runs through real observations in date order. Each frame includes its detector and wavelength, so we can choose close colour matches before comparing positions. The brightness plot samples the smaller orange selection across the cached wavelengths.\n\nThe next step is to compare several well-separated dates and measure the target relative to the same background sources. Which frames would you use as the cleanest reference pair?',
        ['Check several background stars before measuring a shift in the selected region.', 'Keep the crop and brightness scale fixed, and compare observations at similar wavelengths.']),
    'orion-nebula': ('sample-orion-light', 'Different infrared views of the Orion field', 'Jordan Kim',
        'This thread follows the light around the Orion field across the available SPHEREx revisits. I have included the wider image to give the selected patch some context, together with a blink sequence and measurements from the smaller region.\n\nThe brightness plot is a useful starting point for choosing infrared colours to compare. The dots use the same sky selection, with the wavelength evaluated at its centre. The observations span different dates as well as wavelengths, so the frame labels matter when comparing structure.\n\nI would like to compare the brighter part of this field with a quieter neighbouring patch. Does the difference persist when we use closely matched wavelengths and keep the background treatment fixed?',
        ['Some differences can come from changing wavelength coverage rather than changes in the sky.', 'The spectrum and nearby comparison wavelengths are useful checks before naming a chemical feature.']),
    'm31': ('sample-andromeda-core', 'Comparing the inner Andromeda field', 'Alex Rivera',
        'A closer look at the inner Andromeda field in SPHEREx infrared light. The wide observation puts the central selection in context; the orange box defines the patch used for the brightness measurements below.\n\nI have kept the measurements as individual dots so it is easy to see where wavelength coverage is dense and where there are gaps. The blink sequence provides a second view of the same field through the available dates and infrared colours.\n\nA useful follow-up would be to place comparable boxes at increasing distances from the centre and compare their brightness-versus-colour plots. How would you choose a nearby background region that does not remove the galaxy’s own extended light?',
        ['A large galaxy needs extended-source measurements; a point-source aperture will not capture all its light.', 'Could we compare the same box at the same wavelength on more than one date?']),
}


async def main():
    configure_index()
    for target in recommended_targets():
        if target['id'] not in EXAMPLES:
            continue
        ra, dec = key(target['ra'], target['dec'])
        await ensure_shots(None, ra, dec)
        shots = SHOTS[(ra, dec)]
        if not shots:
            raise ValueError(f'No cached observations for {target["name"]}')
        identifier, title, author, body, comments = EXAMPLES[target['id']]
        size = .025
        epochs = sorted({s.epoch_id for s in shots})
        bands = ['starlight']
        from .common import in_band
        if not any(in_band('starlight', s.wavelength) for s in shots):
            bands = ['warm-glow']
        reference = visible_reference([s for s in shots if in_band(bands[0], s.wavelength)], ra, dec)
        if not reference:
            raise ValueError(f'No repeatedly detected reference source in {target["name"]}')
        box = Region(ra=reference['ra'], dec=reference['dec'], width=size, height=size)
        evidence = {'bands': bands, 'epochs': epochs, 'track': [], 'view': {'ra': ra, 'dec': dec, 'fov': .8},
                    'sourceReference': reference, 'sample': True, 'authorId': {'Dr. Maya Rao': 'maya-rao', 'Jordan Kim': 'jordan-kim', 'Alex Rivera': 'alex-rivera'}[author]}
        body = (f'The highlighted reference is a visible image peak matched in {len(reference["positions"])} cached observations in this field. The ring is placed at its measured position in each shown frame.\n\n' + body)
        earliest, latest = min(s.mjd for s in shots), max(s.mjd for s in shots)
        body += f'\n\nObservation set: {len(epochs)} observation IDs, from {mjd_to_iso(earliest)[:10]} to {mjd_to_iso(latest)[:10]}. The image panel and evidence drawer include the frame details for checking or reproducing the comparison.'
        with database() as connection:
            overlap = existing(connection, box)
            if overlap and overlap['id'] != identifier:
                print(f'Skipped {target["name"]}: an existing regional discussion is already present')
                continue
            now = datetime.now(timezone.utc).isoformat()
            previous = connection.execute('SELECT * FROM findings WHERE id=?', (identifier,)).fetchone()
            connection.execute('INSERT OR IGNORE INTO findings VALUES (?,?,?,?,?,?,?,?,?,?)', (
                identifier, box.ra, box.dec, box.width, box.height, title, body, author, now, json.dumps(evidence)))
            if previous and json.loads(previous['evidence']).get('sample'):
                connection.execute('UPDATE findings SET title=?, body=?, ra=?, dec=?, width=?, height=?, evidence=? WHERE id=?', (title, body, box.ra, box.dec, size, size, json.dumps(evidence), identifier))
            for i, text in enumerate(comments):
                connection.execute('INSERT OR IGNORE INTO comments VALUES (?,?,?,?,?)', (
                    f'{identifier}-comment-{i}', identifier, ['Alex Rivera', 'Jordan Kim'][i], text, now))
        attach_media(identifier)
        print(f'Prepared {identifier}: {len(epochs)} observations, real image, data summary and {len(comments)} sample comments')


if __name__ == '__main__':
    asyncio.run(main())
