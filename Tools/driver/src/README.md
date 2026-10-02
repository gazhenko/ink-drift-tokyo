# Driver model sources (CC0)

From the MakeHuman project (https://github.com/makehumancommunity/makehuman), released under
CC0 1.0 Universal (see LICENSE.ASSETS.md in that repository):

- `base.obj` — MakeHuman base mesh (hm08) with joint helper geometry
- `default.mhskel` — default skeleton (joint positions are vertex references into the base mesh)
- `default_weights.mhw` — skin weights for the default skeleton
- `universal-male-young-maxmuscle-averageweight.target` — macro target (applied at 40 %)

`Tools/driver/build_driver.py` cuts the arms out of the body, dresses them in the race suit and gloves,
and rigs them with this skeleton and these weights.
