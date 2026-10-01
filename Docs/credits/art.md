# Art credits — INK DRIFT: TOKYO

All 2D art under `Game/Assets/InkDrift/Art/` (callouts, signs, billboards, vending fronts,
facades, road and livery decals, UI) is generated procedurally by the scripts in `Tools/art/`
(made for this project, no third-party images). Every brand, shop, chain, product and team
name in the art is fictional.

## Fonts

All fonts come from the [google/fonts](https://github.com/google/fonts) repository and are
licensed under the **SIL Open Font License 1.1**. Each family's license text ships next to the
font files in `Game/Assets/InkDrift/Art/Fonts/` as `OFL_<Family>.txt`.
`Tools/art/fetch_fonts.py` downloads them again if needed.

| Family | Files | Copyright (from OFL.txt) | Source | License |
|--------|-------|----------------------|--------|---------|
| Dela Gothic One | `DelaGothicOne-Regular.ttf` | Copyright 2020 The Dela Gothic Project Authors (github.com/syakuzen/DelaGothic) | https://github.com/google/fonts/tree/main/ofl/delagothicone | SIL Open Font License 1.1 |
| Rampart One | `RampartOne-Regular.ttf` | Copyright 2020 The Rampart Project Authors (github.com/fontworks-fonts/Rampart) | https://github.com/google/fonts/tree/main/ofl/rampartone | SIL Open Font License 1.1 |
| Reggae One | `ReggaeOne-Regular.ttf` | Copyright 2020 The Reggae Project Authors (github.com/fontworks-fonts/Reggae) | https://github.com/google/fonts/tree/main/ofl/reggaeone | SIL Open Font License 1.1 |
| Bangers | `Bangers-Regular.ttf` | Copyright 2010 The Bangers Project Authors (github.com/googlefonts/bangers) | https://github.com/google/fonts/tree/main/ofl/bangers | SIL Open Font License 1.1 |
| Chakra Petch | `ChakraPetch-Bold.ttf`, `ChakraPetch-Regular.ttf` | Copyright 2018 The Chakra Petch Project Authors (github.com/m4rc1e/Chakra-Petch) | https://github.com/google/fonts/tree/main/ofl/chakrapetch | SIL Open Font License 1.1 |
| Noto Sans JP | `NotoSansJP-VariableFont_wght.ttf`, plus `NotoSansJP-Black.ttf` / `NotoSansJP-Bold.ttf` (static instances at wght 900 / 700 made with fontTools `instancer`) | Copyright 2014-2021 Adobe (Reserved Font Name 'Source'); Noto Sans JP | https://github.com/google/fonts/tree/main/ofl/notosansjp | SIL Open Font License 1.1 |

Raw download base used: `https://raw.githubusercontent.com/google/fonts/main/ofl/<family>/`.
Under the OFL, the static Noto Sans JP instances are modified versions. They keep the original
copyright notice and license, and they don't use any Reserved Font Name.

## Tooling (not shipped)

skia-python (BSD-3-Clause), Pillow (MIT-CMU), NumPy, SciPy and scikit-image (BSD-3-Clause),
OpenCV (Apache-2.0) and fontTools (MIT) run the generators. None of them ship with the game.
