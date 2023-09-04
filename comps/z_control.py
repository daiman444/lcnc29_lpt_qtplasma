#!/usr/bin/env python3

import hal


c = hal.component('hcontrol')
c.newpin('in', hal)
c.ready()
while True:
    pass