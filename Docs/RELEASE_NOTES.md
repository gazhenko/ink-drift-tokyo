# INK DRIFT: TOKYO — v1.23.0: sharper baked shading

A comic-book cel-shaded drift racer through Tokyo. **Watch the trailer:** [INK-DRIFT-TOKYO-trailer.mp4](https://github.com/gazhenko/ink-drift-tokyo/releases/download/v1.0.0/INK-DRIFT-TOKYO-trailer.mp4).

## What's new in 1.23.0
- **Sharper shading on the gloves and sleeves.** The driver's baked ambient occlusion (the soft darkening in creases, between fingers and under the gauntlet) was squeezed into a seventh of its texture, because every one of the thousands of stitch beads and vent holes had its own patch. Stitches, vents and decals are now left out of the bake, so the gloves and sleeves get the whole texture at about seven times the resolution.
- **No false shadow under the decals.** The glove logo and suit patches float a fraction of a millimetre above the surface, and the bake treated them as solid, so the leather showing through the clear parts of a logo was darkened. It no longer is.

## 1.22.0: leather that reads as leather
- **Finished leather.** Real glove leather has two highlights: a broad, soft one from the hide and a tighter, fainter one from its finish, broken up by the grain. The gloves had only the first and looked like matte rubber. They now have both, so the gauntlets and knuckle guards show a satin sheen as they turn under the cabin and street lights.
- **Every light counts.** The leather's finish and the suit's fabric sheen now respond to every cabin and street light, not just the sun, so neon at night shows on the gloves and sleeves too.

## 1.21.0: the body moves with the car
- **Shoulders that sway.** Under braking, acceleration and cornering, the driver's shoulders now move with the head instead of staying fixed in the car. The hands stay on the wheel and the elbows take up the motion, as they would for a real driver held in a seat.
- **Embroidered glove straps.** The INK RACEWEAR wordmark is now also stitched along each glove's wrist strap, matching the sleeves.

## 1.20.0: embroidered sleeves
- **Embroidered sleeves.** "INK RACEWEAR" is now satin-stitched in white thread along the top of each forearm, just above the glove. It sits where you see it from the driver's seat, with raised thread relief that catches the light as real embroidery does, and the sleeve's folds stop where the stitching stiffens the cloth.
- **Fixed: the sleeve patch read backwards on one arm.** Suit and glove decals are now turned round rather than mirrored when they're placed, so the INK DRIFT patch reads correctly on both sleeves.

## 1.19.0: anatomical fingers
- **Fingers with real proportions.** Real fingers are wider than they are deep, roughly 20 mm across by 17 mm from nail to pad. The base model's were almost round, which made the gloved hand look swollen. Each finger and the thumb is now flattened about 14% along the nail-to-pad axis, following each finger's own direction and blending smoothly over the joints.

## 1.18.0: multisampled edges
- **Multisample anti-aliasing.** The finest geometry in the car is narrower than a pixel at 1080p: glove and wheel stitching, the rim's edges, the shift lever. It used to break up into jagged dashes and crawl as the view moved. High quality now renders with 4x MSAA and Medium with 2x, on top of the existing SMAA, so the stitches read as clean, steady lines. Low quality is unchanged.

## 1.17.0: a sleeve that bunches
- **The suit sleeve gathers at the glove.** Where the glove's gauntlet closes over the sleeve, the race suit now piles up into a soft bulge of uneven folds, like real fabric pushed up the forearm, instead of running into the glove as a smooth tube.
- The sewn-on INK DRIFT patch stays flat over the folds, because a patch stiffens the cloth it covers.

## 1.16.0: stitched thumbs and fingertips
- **Seams over every fingertip.** The twin side seams on each finger now continue over the tip in one unbroken seam, as on a real glove.
- **A stitched thumb.** The thumb, the part you see most as it lies over the spoke at 9 and 3, gets seams along both sides and over its tip, following the way the thumb is turned.

## 1.15.0: contact shadows in the cockpit
- **Contact shadows inside the car.** The in-car view now has ambient occlusion where things touch or nearly touch: fingers wrapped round the rim, the glove against the wheel, gauges in their binnacle, the shifter in its boot. In a cabin lit mostly by soft light from outside, this is what keeps the hands from looking pasted onto the wheel.
- It only runs while you're in the in-car view (on High and Medium quality), and the comic city outside the windows keeps its own look.

## 1.14.0: no more flare in the mirror view
- **Fixed: a white blob in the look-back view.** Looking back over your shoulder could show a huge white flare at the rear quarter window. A trim panel's surface normals collapsed to zero, so the panel rendered infinitely bright and the bloom spread it over half the screen. The panel's normals are now built correctly, and the cockpit shader guards against degenerate normals.
- **Glints stay in proportion.** Mirror-smooth parts catching the sun (chrome bezels, bolts, the polished master cylinder) are capped at a bright but finite level, so a sun glint is a sparkle rather than a screen-wide bloom.

## 1.13.0: a living grip
- **The hands are no longer frozen.** Each finger drifts slightly and slowly on the rim. The grip tightens when you steer hard, and when the wheel is calm a hand now and then lets go a touch and takes hold again, as a real driver does.

## 1.12.0: what the hands hold
- **A modelled shifter.** A 46 mm round black knob with the gear pattern (R 1 3 5 / 2 4 6) in white on top, a chrome lever and jam nut. Around it sits a leather boot gathered into soft, uneven folds with twin-stitched corner seams, and a satin trim bezel with four screws.
- **A modelled hydraulic handbrake.** An anodised lever in the car's accent colour with a ribbed rubber grip and end cap, on a cover plate with bracket cheeks, a polished master cylinder with its reservoir, and braided lines running into the console.
- **Gloves that crease.** The leather now bunches into folds on the palm side of each finger joint, wrinkles over the knuckles, and gathers in soft folds round the wrist, where it used to be perfectly smooth.

## 1.11.0: cleaner materials
- **No more sparkling edges.** Gloves, suit and the leather and suede in the cockpit glittered with bright specks along their edges. Each grain of the material near the silhouette reflected the sky at full strength. Reflections now take their Fresnel from the smooth surface and drop any reflection that would point back into the material, so edges stay clean.
- **Finer glove leather.** The glove backs and knuckle guards now have the fine grain of thin driving-glove nappa instead of coarse upholstery hide.
- **A real silicone grip print.** The palm's grip dots are smaller and stand only slightly proud, as a printed pattern does, instead of reading as bumpy skin.

## 1.10.0: a natural grip
- **A natural grip on the wheel.** At 9 and 3 o'clock the driver's wrists were bent about 100 degrees, further than a real wrist can go, so the gloves folded like a bent hose. Each fist now settles on the rim as a real hand does. It sits on the outside of the rim with the knuckles forward and the rim running diagonally across the palm, and the thumb lies over the spoke.
- **The wrist stays within a comfortable bend** (about 40 degrees) in every position on the rim. The grip adjusts smoothly as the wheel turns and as the hands move hand over hand.

## 1.9.0: a clean cockpit
- **No more comic outlines inside the car.** The realistic cockpit and driver were meant to be kept free of the comic ink lines and paper grain, but the shipped builds since 1.5.0 were missing that render pass. Now the cockpit and driver are clean, and the comic look stays on the city outside the windows.
- **The stitching shows its real colour.** Because the ink lines no longer cover it, the red contrast thread on the gloves, suit cuffs, dash and wheel now shows as red.
- **Thumbs over the spokes.** At 9 and 3 o'clock each thumb now hooks over the wheel spoke, the classic racing hold. The thumb lets go when that hand moves round the rim.
- **Fix:** the game no longer logs a mesh-read error when the driver loads.

## 1.8.0: glove construction
- **Segmented knuckle guard.** The red guard is now four separate padded segments with grooves between the knuckles, like real racing gloves, so it flexes and reads as padding rather than one block.
- **External finger seams.** Twin rows of stitching run down both sides of every finger (about 300 more stitches), following the finger bones so they bend with the hand.
- **Vent perforations.** Rows of vent holes on the backs of the fingers, as on lightweight racing gloves.

## 1.7.0: a moulded cockpit
- **A moulded dashboard.** The dash is now one smooth skin that runs from the windshield base over the crest, round the lip and down the face, with a twin-needle stitched leather seam across its full width.
- **Rounded trim everywhere you look:** the A-pillar trims, header rail, centre stack, console and glovebox lid have softly rounded edges instead of hard boxes.
- **More stitching:** stitched edges along the console top and the door cards.

## 1.6.0: stitched gloves and a modelled wheel
- **Real stitching.** Twin-needle thread geometry runs along every panel seam: about 1,500 stitches on the gloves (red contrast thread round the knuckle guard, palm, strap and gauntlet) and about 970 on the suit (along the stripe and cuffs).
- **Better-fitting gloves.** The leather hugs the fingers tighter than the palm, so the fingers are slimmer and more anatomical.
- **A modelled deep-dish steering wheel**, built in Blender:
  - a 350 mm rim with a shaped oval section that thickens at the 9 and 3 o'clock thumb grips
  - an Alcantara cover with an inner seam groove and baseball stitching, and a 12 o'clock marker band
  - three tapered, dished spokes with drilled lightening holes
  - six hex bolts, a horn button with a centre ring, a quick-release collar and pull ring

## 1.5.0: photo-scanned driver and cockpit
- **Photo-scanned materials.** The driver's gloves and suit now use CC0 photo-scans from Poly Haven at their real-world scale:
  - full-grain leather for the glove backs and knuckle guards
  - scanned suede for the palms, with the silicone grip print on top
  - a scanned technical weave under the suit's quilting
  - scanned knit for the cuffs

  Each scan is tinted to the suit colours while keeping its own natural variation.
- **A realistic cockpit around the hands.** The whole interior now uses the same physically based, photo-scanned rendering as the driver, so the hands sit in a consistent realistic space. The game's comic ink filter stays off everything inside the car; the city outside keeps the comic style.
  - grain-embossed dash
  - Alcantara wheel rim, headliner and visors
  - stitched leather door cards
  - herringbone seat fabric and floor carpet
  - brushed metal and chrome fittings
  - a powder-coated roll cage
- **Real shadows across the cockpit:** the wheel, cage and pillars now cast shadows onto the dash and the driver's hands.
- **Interior lighting:** the cabin now blocks reflections of the street the way a real roof and doors do (specular occlusion), so the fabric reads as matte cloth and the leather as satin, even under Shibuya's neon. Cloth reflects almost nothing; metal fittings keep their reflections.
- **Verified on Linux:** the Linux build was run headless on Linux with OpenGL 4.5 software rendering and renders the same in-car view as macOS.

## 1.4.0: a realistic driver
- **Realistic driver shading.** The driver now has its own physically based shader:
  - Realistic lighting with soft shadows, cabin and street lights, and reflections.
  - Cloth sheen on the suit and satin leather on the gloves.
  - The game's comic ink outlines and grain are masked off the driver, so the gloves and sleeves sit in the comic cockpit like a photographed object.
- **Real shadows:** the hands cast shadows onto the wheel, dash and each other, and pick up the car's roof and pillar shadows.
- **Baked detail:**
  - Ambient occlusion, convexity and cavity are baked from the high-detail mesh, so the gaps between fingers, the seams, the cuff edges and the strap all darken naturally.
  - The leather is lightly scuffed on its high points.
- **A truer glove:** smoothed fingertips with no fingernail bumps, double flexion creases across the palm side of every finger joint, and fine wrinkles over the knuckles.
- **A real 9-and-3 grip:**
  - From the driver's seat you see the backs of the gloves, with the logo and red knuckle guards facing you.
  - The index finger is on top, the fingers wrap round the rim and the thumbs hook over it.
  - When a hand lets go to re-grab, it lifts off the rim instead of passing through it.
- **Instrument glow:** the gauges spill a faint warm light onto the gloves and rim at night.

## 1.3.0: the driver
- **A real driver in the in-car view.** The capsule arms are replaced by a fully rigged human model with anatomically correct arms and hands. It is built from the MakeHuman CC0 base mesh with that project's own skeleton and hand-painted skin weights, scaled to a 1.75 m adult.
- **Race suit and gloves, detailed to the stitch:**
  - The suit sleeves are quilted multi-layer Nomex with a contrasting stripe down the top of the arm, fabric folds at the elbow, and embroidered patches.
  - The leather gloves have a pebbled grain, a suede palm with a printed silicone grip, a padded knuckle guard and a flared gauntlet with a Velcro strap and pull tab. Every panel meets at a stitched seam groove.
- **Hands that actually hold things.**
  - Each finger joint curls about its anatomical axis, so the fingers wrap the wheel rim with the thumb over the top.
  - The left hand cups the shift knob and closes round the hydraulic handbrake. Hands open as they let go and close again on the next hold.
  - Two-bone arm IK keeps the elbows hinging the natural way, and the forearm's twist bone shares the wrist roll so the wrist never pinches.
- **Realistic shading for the driver:** a soft light-to-shadow transition and real leather sheen, while the rest of the game keeps its comic look.

## 1.2.0: in-car view
- **In-car camera from the driver's seat.** Press **C / Y / △** to cycle cameras: chase, near chase, **in-car**, roof, bumper. The game remembers your choice.
- **Right-hand drive, like the real Japanese cars.** Each car gets its own cockpit, sized from its windshield, roof and beltline. It includes a deep-dish wheel, an instrument pod with live tach, boost and water gauges, a digital gear and speed readout, a shift-light strip that flashes at the limiter, an H-pattern shifter, a hydraulic handbrake, bucket seats with harnesses, a roll cage in the car's colour, sun visors, door cards, and a rear-view mirror that shows the cars behind you.
- **The driver's arms are rendered and animated.**
  - The hands grip the rim and steer hand over hand.
  - When the wheel snaps back on its own in a drift, it spins through the palms.
  - The left hand moves the gear lever through the H-pattern on every shift and pulls the hydraulic handbrake.
- **The camera feels the car.** Your head moves with braking, acceleration and cornering forces, and turns to look where the car is sliding. Hold look-back to turn round over the seats.
- In the car the HUD drops its speedo and drift meter (the dash shows them) and moves the minimap out of the way.

## 1.1.0: controllers and remapping
- **Controllers work everywhere.** Xbox (360 / One / Series / any XInput pad), DualShock 4, DualSense and Switch Pro are recognised directly. Generic USB/Bluetooth pads that only show up as a joystick are turned into a standard gamepad automatically: DirectInput-mode pads, Xbox-style clones on macOS, and unrecognised pads on Linux.
- **Controller Setup** (Settings ▸ Controls) records any controller's layout one button at a time and remembers it per controller. Use it when a pad's buttons come out wrong, or to map a racing wheel and pedals.
- **Full remapping.** Every driving control has two keyboard keys and one controller input. You set one by pressing it. If that input was already used somewhere else, it's removed there. You can clear or reset a single slot, or reset everything. Bindings are saved between sessions.
- **Button prompts match your device.** Prompts switch between keyboard and controller as you play, and use your controller's own names: A/B/X/Y, ×/○/□/△ or B/A/Y/X.
- **Controller options:** stick dead zone, steering response (linear / smooth / soft), vibration, and button labels. The new **Input test** panel shows live input.
- **Vibration** on tyre slide, the rev limiter and wall hits.
- **Pause menu:** Controls are available mid-race, B / ○ backs out, and unplugging the controller pauses the game.
- Menus: selection no longer jumps between buttons on the car-select screen when changing car or paint with the d-pad. A gamepad user who clicked the mouse gets a selection back.

## Downloads
| Platform | File | Notes |
|---|---|---|
| macOS (Apple Silicon + Intel) | `InkDriftTokyo-v1.8.0-macOS-universal.zip` | Unsigned (ad-hoc). Right-click → Open, or run `xattr -dr com.apple.quarantine "INK DRIFT TOKYO.app"` |
| Windows 10/11 x64 | `InkDriftTokyo-v1.8.0-Windows-x64.zip` | Extract everything into a new folder, run `InkDriftTokyo.exe` (D3D11 default) |
| Linux x64 | `InkDriftTokyo-v1.8.0-Linux-x64.tar.gz` | Extract into a new folder, then `./InkDriftTokyo.x86_64` (Vulkan, OpenGL fallback) |

Checksums: `SHA256SUMS.txt`.

## What's in the demo
- **3 tracks:** SHIBUYA NEON (night, wet neon streets, sakura canal) · SHUTO C1 LOOP (sunset elevated expressway with traffic) · OKUTAMA TOUGE (autumn mountain switchbacks)
- **5 cars**, all fictional ricer-kitted look-alikes: HACHI GR8 · KAIJU SPR-X · ZENKAI Z · RAIJIN BX-R (AWD) · TSUBAME RS — 8 paints each
- **Modes:** Drift Attack · Rival Battle (5 drifting AI rivals) · Free Run
- **Drift physics** with combined-slip tires, clutch kicks, handbrake, weight transfer; assists from PRO (none) to EASY
- **Drift callouts:** graffiti comic pop-ups — ナイス！ 成功！ グレートドリフト！ すごい！ やばい！！ 完璧！ 神ドリフト！！ — with a Japanese announcer voice

## Default controls
| | Keyboard | Xbox | PlayStation |
|---|---|---|---|
| Throttle / Brake | W / S or ↑ / ↓ | RT / LT | R2 / L2 |
| Steer | A / D or ← / → | Left stick | Left stick |
| Handbrake | Space | A | × |
| Clutch | Left Shift | X | □ |
| Shift up / down | E / Q | RB / LB | R1 / L1 |
| Camera · Look back · Reset | C · B · R | Y · RS · View | △ · R3 · Create |
| Pause | Esc / P | Menu | Options |

## Known limitations
- Builds are unsigned; macOS/Windows will warn on first launch.
- Tested natively on macOS (Apple Silicon); the Linux build is verified rendering on Linux (OpenGL, software). The Windows build is produced by the same pipeline but hasn't been run on Windows hardware. Controller support is covered by automated tests with simulated devices.
- Wired third-party Xbox-protocol pads that macOS itself doesn't expose to apps can't be seen by any game on macOS; connect over Bluetooth or switch the pad to its DirectInput/Switch mode.
- The announcer voice is Japanese text-to-speech; the voice lines can be regenerated with `Tools/audio/elevenlabs_voices.py`.
