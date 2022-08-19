from opentrons import protocol_api
import opentrons.execute
import opentrons.simulate
from opentrons import types #for custom pipette positioning
import time #for countdown timing
import datetime #for more timing
import json

metadata = {"apiLevel" : "2.12"}
protocol = opentrons.execute.get_protocol_api('2.12')

protocol.home()

## LOADED VOLUMES ##
spri_stock_vol  = 4000  #3600 required, 5k for safety
eb_stock_vol    = 4000  #1928 required, 5k for safety
elu_stock_vol   = 2000  #this value does not effect multi setup, lots extra required for multi reservior
eth_stock_vol   = 20000 #24400 required, 27.5k for safety. Value is lower to account for evaporation

def run(protocol: protocol_api.ProtocolContext):
    
    ## HARDWARE ##
    t20_0  = protocol.load_labware('opentrons_96_tiprack_20ul', 9)
    t20_1  = protocol.load_labware('opentrons_96_tiprack_20ul', 6)
    t300_0 = protocol.load_labware('opentrons_96_tiprack_300ul', 2)
    t300_1 = protocol.load_labware('opentrons_96_tiprack_300ul', 5)
    t300_2 = protocol.load_labware('opentrons_96_tiprack_300ul', 8)
    t300_3 = protocol.load_labware('opentrons_96_tiprack_300ul', 11)
    r15 = protocol.load_labware('nest_12_reservoir_15ml', 3)
    mag = protocol.load_module('magnetic module gen2', 4)
    with open('custommagplate96s_96_wellplate_100ul.json') as labware_file: #labware def with this title in directory
        labware_def = json.load(labware_file)
        mag_plate = mag.load_labware_from_definition(labware_def)
    tc = protocol.load_module("thermocycler module", configuration='semi')
    tc_plate = tc.load_labware('nest_96_wellplate_100ul_pcr_full_skirt')
    temp_plate = protocol.load_labware('opentrons_96_aluminumblock_generic_pcr_strip_200ul', 1)

    t20_racks = [t20_0, t20_1]
    t300_racks = [t300_0, t300_1, t300_2, t300_3]

    ## PIPETTES ##
    p20  = protocol.load_instrument('p20_multi_gen2', mount = 'left', tip_racks=t20_racks)
    p300 = protocol.load_instrument('p300_multi_gen2', mount = 'right', tip_racks=t300_racks)

    ## SETUP ##
    p300.starting_tip=t300_0['A1']        #accomidates SPRIselect mixing tip reuse 

   ## OFFSETS ##
    t20_0.set_offset(x=-0.1, y=1.0, z=-7.1)
    t20_1.set_offset(x=0.2, y=0.8, z=-7.1)
    t300_0.set_offset(x=0.4, y=0.5, z=-6.8)
    t300_1.set_offset(x=0.3, y=0.4, z=-6.8)
    t300_2.set_offset(x=0.3, y=0.5, z=-6.8)
    t300_3.set_offset(x=0.3, y=0.5, z=-6.8)
    #tb1_5.set_offset(x=0.6, y=1.3, z=0.9)
    r15.set_offset(x=0.3, y=0, z=-0.4)
    tc_plate.set_offset(x=-22.8, y=0.9, z=0.2)
    temp_plate.set_offset(x=0.4, y=1.1, z=82.2)
    mag_plate.set_offset(x=-0.1, y=0.7, z=-0.3)

    ## MAG WET CALIBRATION ##
    mag_z = 16.0                        #mag pelleting height
    well_300_nomag = (0, 0, -19.8)      #
    well_300_mag   = (-0.1, 0.5, -16.7)
    well_20_nomag  = (0, 0, -19.8)
    well_20_mag    = (-0.1, 0.5, -16.7)

    ## SUBMETHODS ##
    def getEthStock():
        global eth_stock_vol
        if eth_stock_vol > 20000:
            return eth_stock
        elif eth_stock_vol > 10000:
            return eth2_stock
        else:
            return eth3_stock

    def eth_wash_drain(
        _eth_stock: protocol_api.labware.Well,
        _well: protocol_api.labware.Well,
        _w = []): #_w is array of wash volumes: [300, 200] for 2-stage wash with 2 dif. volumes
        
        global eth_stock_vol

        _well_300_mag = _well.top().move(types.Point(
            x=well_300_mag[0],
            y=well_300_mag[1],
            z=well_300_mag[2]))

        for w in _w:
            p300.pick_up_tip()
            #Below spaghetti code accounts for max tip volume of 250ul, allows for washes @300ul as per protocol
            if w <= 230:
                p300.aspirate(w, _eth_stock.bottom(z=2))    #Pull from above bottom of eth stock to prevent vacuum
                p300.move_to(_eth_stock.top(z=5))           #
                p300.air_gap(20)                            #
                p300.touch_tip()                            #
                protocol.delay(seconds=3)                   #allows drips from low-viscosity liquid
                p300.move_to(_well.top())
                p300.dispense(w, _well_300_mag, rate=0.2) 
                p300.move_to(_well.top())
                p300.blow_out()
            if w > 230:
                for i in range(2):
                    p300.aspirate(w/2, _eth_stock.bottom(z=2)) 
                    p300.move_to(_eth_stock.top(z=5))           
                    p300.air_gap(20)                            
                    p300.touch_tip()                            
                    protocol.delay(seconds=3)
                    p300.move_to(_well.top())
                    p300.dispense(w/2, _well_300_mag, rate=0.2)
                    p300.move_to(_well.top())
                    p300.blow_out()
                    if i == 0:
                        p300.drop_tip()
                        p300.pick_up_tip()
            _awash: float
            if w < 230:
                _awash = w - 20
            else:
                _awash = 230

            print("current eth_stock: " + str(eth_stock_vol))
            eth_stock_vol = eth_stock_vol - (w*8)
            print("subtracted eth_stock: " + str(eth_stock_vol))
            
            print("eth wash starting:")
            print(datetime.datetime.now())
            wash_time = 20                      #20 sec wash time, 10 sec mag sep time (perhaps excessive?)
            wash_start = time.monotonic()
            while time.monotonic() < wash_start + wash_time:
                p300.aspirate(_awash, _well_300_mag, rate=0.2)
                p300.dispense(_awash, _well_300_mag, rate=0.2)
            print(datetime.datetime.now())
            protocol.delay(seconds=10)
            if w < 230:
                p300.aspirate(w + 10, _well_300_mag, rate=0.2)       
                protocol.delay(seconds=1)
                p300.move_to(_well.bottom(z=2), speed = 1)
                p300.drop_tip()
            if w >=230:
                for i in range(2): 
                    p300.aspirate(w/2 + 10, _well_300_mag, rate=0.2)
                    protocol.delay(seconds=1)
                    p300.move_to(_well.bottom(z=2), speed = 1)
                    p300.dispense(w/2 + 10, protocol.fixed_trash['A1'])
                p300.drop_tip()
        print("pellet air dry has started: " + str(datetime.datetime.now()))

    def vacuum_aspirate_transfer(
        _asp_pos: types.Point,
        _asp_spd: float,
        _vol: float,
        _dest: types.Point,
        _blow_pos: types.Point,
        _reps: int):
        for _ in range(_reps):
            p20.aspirate(_vol, _asp_pos, rate=_asp_spd)
            protocol.delay(seconds=0.5)
            p20.default_speed=1
            p20.move_to(_asp_pos.move(types.Point(z=3)))
            p20.default_speed=400
            p20.dispense(_vol, _dest)
            protocol.delay(seconds=0.5)
            p20.blow_out(_blow_pos)
            p20.touch_tip()

    #use p20 with pre-loaded tip before calling (reduce tip waste)
    #resolves with fresh p20 loaded in every condition
    def resusp_pel_mix_inc_mag(
        _mag_well: protocol_api.labware.Well,
        _mix_vol: float,
        _tot_vol: float,
        _inc_sec: int,
        _mag_sec: int):

        _well_300_nomag = _mag_well.top().move(types.Point(
            x=well_300_nomag[0],
            y=well_300_nomag[1],
            z=well_300_nomag[2]))

        for _ in range(30):
            p300.aspirate(_mix_vol, _well_300_nomag)
            p300.dispense(_mix_vol, _well_300_nomag)
        protocol.delay(seconds=1)
        p300.move_to(_well_300_nomag.move(types.Point(z=getMagWellHeight(_tot_vol + 80))), speed=2)
        protocol.delay(seconds=1)
        p300.blow_out()

        print("incubation starting: " + str(_inc_sec))
        inc_start = time.monotonic()
        while time.monotonic() < inc_start + _inc_sec:
            p300.aspirate(_mix_vol - 20, _well_300_nomag, rate=0.2)
            p300.dispense(_mix_vol - 20, _well_300_nomag, rate=0.2)
        print(datetime.datetime.now())
        print("incubation finished")

        p300.move_to(_well_300_nomag.move(types.Point(z=getMagWellHeight(_tot_vol + 80))), speed=2)
        protocol.delay(seconds=1)
        p300.blow_out()

        print("magnet engaged")
        mag.engage(height=mag_z)
        p300.drop_tip()
        protocol.delay(seconds=_mag_sec)

    #position is adjustment from bottom of well
    def getMagWellHeight(vol: float):
        if vol <= 100:
            return vol*0.08
        else:
            return 0.08*100 + (vol-100)*0.045
    
    def getEppendorf_1_5Height(vol: float):
        #TODO: add volume-dependent vertical correction factor when aspirating, but without crushing tip when vol is close to 0
        #0.031327068 mm/ul up to and including 500ul
        #0.019030677 mm/ul after
        #if vol <= 500:
        #    return vol*0.031
        #else:
        #    return 500*0.031 + (vol-500)*0.019

        #multi setup does not use eppendorf_1_5s, disabling for now
        return 0

    def spri_stock_mix():
        if spri_stock_vol < 2000:
            for _ in range(20):
                p300.aspirate(spri_stock_vol/8 - 10, spri_stock.bottom(z=1), rate = 2.0)
                p300.dispense(spri_stock_vol/8 - 10, spri_stock.bottom(z=1), rate = 2.0)
            p300.move_to(spri_stock.top())
            protocol.delay(seconds=1)
            p300.touch_tip()
            p300.blow_out()
        else:
            for _ in range(20):
                p300.aspirate(240, spri_stock.bottom(z=1), rate = 2.0)
                p300.dispense(240, spri_stock.bottom(z=1), rate = 2.0)
            for _ in range(10):
                p300.aspirate(240, spri_stock.bottom(z=1), rate = 2.0)
                p300.dispense(240, spri_stock.bottom(z=1), rate = 2.0)
            p300.move_to(spri_stock.top())
            protocol.delay(seconds=1)
            p300.touch_tip()
            p300.blow_out()
        p300.touch_tip()

        p300.return_tip()
        p300.pick_up_tip()
            

    def spri_stock_mix_transfer(
        vol: float,
        dest: protocol_api.labware.Well,
        dest_vol: float):

        #position adjustments have local scope so specific `dest` well can be referenced
        _well_300 = dest.top().move(types.Point(
            x=well_300_nomag[0],
            y=well_300_nomag[1],
            z=well_300_nomag[2]))
        _well_20  = dest.top().move(types.Point(
            x=well_20_nomag[0],
            y=well_20_nomag[1],
            z=well_20_nomag[2]))
        
        global spri_stock_vol

        if vol > 250 or vol < 0:
            raise Exception ("SPRI transfer volume must be between 0 and 250ul")

        if vol <= 40:
            #mix:
            spri_stock_mix()
            #pre-wet
            for _ in range(1):
                p20.aspirate(20, spri_stock.bottom(z=getEppendorf_1_5Height(spri_stock_vol)))
                p20.dispense(20, spri_stock.bottom(z=getEppendorf_1_5Height(spri_stock_vol)))
            if vol <= 20:
                p20.aspirate(vol, spri_stock.bottom(z=getEppendorf_1_5Height(spri_stock_vol - vol)), rate=0.25)
                protocol.delay(seconds=1)
                p20.move_to(spri_stock.top(), speed=10)
                p20.dispense(vol, _well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol))), rate=1.0)
                protocol.delay(seconds=1)
                p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol + 80))), speed = 4.4)
                p20.blow_out()
                p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol))), speed = 4.4)
                p20.move_to(dest.top())
            else:
                for i in range(2):
                    p20.aspirate(vol/2, spri_stock.bottom(z=getEppendorf_1_5Height(spri_stock_vol - i*(vol/2))), rate=0.25)
                    protocol.delay(seconds=1)
                    p20.move_to(spri_stock.top(), speed=10)
                    p20.dispense(vol/2, _well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i+1)*(vol/2)))), rate=1.0)
                    protocol.delay(seconds=1)
                    p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i+1)*(vol/2) + 80))), speed = 4.4)   #slowly +Z pipette, pulling droplet out of tip
                    protocol.delay(seconds=1)
                    p20.blow_out()                                                                  #blows bubble out tip
                    p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i)*(vol/2)))), speed = 4.4)          #merges bubble with liquid surface
                    p20.move_to(dest.top())
                    p20.drop_tip()
                    p20.pick_up_tip()
        else:
            #mix:
            spri_stock_mix()
            for _ in range(1):
                p300.aspirate(vol, spri_stock.bottom(z=getEppendorf_1_5Height(spri_stock_vol)))
                p300.dispense(vol, spri_stock.bottom(z=getEppendorf_1_5Height(spri_stock_vol)))
            p300.aspirate(vol, spri_stock.bottom(z=getEppendorf_1_5Height(spri_stock_vol - vol)), rate = 0.2)
            protocol.delay(seconds=1)
            p300.move_to(spri_stock.top(), speed=10)
            p300.dispense(vol, _well_300.move(types.Point(z=getMagWellHeight(dest_vol + vol))), rate=0.2)
            protocol.delay(seconds=1)
            p300.move_to(_well_300.move(types.Point(z=getMagWellHeight(dest_vol + vol + 80))), speed = 4.4)
            protocol.delay(seconds=1)
            p300.blow_out()
            p300.move_to(dest.top())
            p300.drop_tip()
            p300.pick_up_tip()


       

        print("current spri_stock: " + str(spri_stock_vol))
        spri_stock_vol = spri_stock_vol - vol*8
        print("subtracted spri_stock: " + str(spri_stock_vol))

        
    
    def cDNA_transfer(
        source: protocol_api.labware.Well,
        vol: float,
        dest: protocol_api.labware.Well,
        dest_vol: float):
        #source: 8-tube strip on temp block
        #dest: disengaged mag well
        #TODO track height changes from liquid in tubestrips on temp plate

        #position adjustments have local scope so specific `dest` well can be referenced
        _well_300 = dest.top().move(types.Point(
            x=well_300_nomag[0],
            y=well_300_nomag[1],
            z=well_300_nomag[2]))
        _well_20  = dest.top().move(types.Point(
            x=well_20_nomag[0],
            y=well_20_nomag[1],
            z=well_20_nomag[2]))

        if vol > 250 or vol < 0:
            raise Exception ("cDNA transfer volume must be between 0 and 250ul")
        
        if vol <= 40:
            #transfer, pull up, blow out, touch liquid line
            if vol <= 20:
                for _ in range(1):
                    p20.aspirate(vol, source.bottom(z=0.5))
                    p20.dispense(vol, source.bottom(z=0.5))
                p20.aspirate(vol, source.bottom(), rate=0.25)
                protocol.delay(seconds=1)
                p20.move_to(source.bottom(z=5), speed=1)
                p20.move_to(source.top(), speed=4.4)
                p20.touch_tip()
                p20.dispense(vol, _well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol))), rate=0.25)
                protocol.delay(seconds=0.5)
                p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol + 80))), speed = 4.4)
                protocol.delay(seconds=0.5)
                p20.blow_out()
                p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol))))
                p20.move_to(dest.top())
            else:
                for _ in range(1):
                    p20.aspirate(20, source.bottom(z=0.5))
                    p20.dispense(20, source.bottom(z=0.5))
                for i in range(2):
                    p20.aspirate(vol/2, source.bottom(z=0.5), rate=0.25)
                    protocol.delay(seconds=1)
                    p20.move_to(source.bottom(z=2), speed=1)
                    p20.move_to(source.top(), speed=4.4)
                    p20.dispense(vol/2, _well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i+1)*(vol/2)))), rate=0.25)
                    protocol.delay(seconds=0.5)
                    p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i+1)*(vol/2) + 80))), speed = 4.4)#slowly +Z pipette, pulling droplet out of tip
                    protocol.delay(seconds=0.5)
                    p20.blow_out()                                                                              #blows bubble out tip
                    p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i)*(vol/2)))))       #merges bubble with liquid surface
                    p20.move_to(dest.top())
            p20.drop_tip()
            p20.pick_up_tip()
        else:
            for _ in range(1):
                p300.aspirate(vol, source.bottom(z=0.5))
                p300.dispense(vol, source.bottom(z=0.5))
            p300.aspirate(vol, source.bottom(z=0.5), rate = 0.2)
            protocol.delay(seconds=1)
            p300.move_to(source.bottom(z=2), speed=1)
            p300.move_to(source.top(), speed=4.4)
            p300.dispense(vol, _well_300.move(types.Point(z=getMagWellHeight(dest_vol + vol))), rate=0.2)
            protocol.delay(seconds=1)
            p300.move_to(_well_300.move(types.Point(z=getMagWellHeight(dest_vol + vol + 80))), speed = 4.4)
            protocol.delay(seconds=1)
            p300.blow_out()
            p300.move_to(dest.top())
            p300.drop_tip()
            #p300.pick_up_tip() #removed so SPRIselect tip may occasionally be used

    def eb_stock_transfer(
        vol: float,
        dest: protocol_api.labware.Well,
        dest_vol: float):

        global eb_stock_vol

        #position adjustments have local scope so specific `dest` well can be referenced
        _well_300 = dest.top().move(types.Point(
            x=well_300_nomag[0],
            y=well_300_nomag[1],
            z=well_300_nomag[2]))
        _well_20  = dest.top().move(types.Point(
            x=well_20_nomag[0],
            y=well_20_nomag[1],
            z=well_20_nomag[2]))
        
        if vol > 250 or vol < 0:
            raise Exception ("EB transfer volume must be between 0 and 250ul")

        if vol <= 40:
            #pre-wet
            for _ in range(1):
                p20.aspirate(20, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol)))
                p20.dispense(20, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol)))
            if vol <= 20:
                p20.aspirate(vol, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol - vol)), rate=0.25)
                protocol.delay(seconds=1)
                p20.move_to(eb_stock.top(), speed=10)
                p20.dispense(vol, _well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol))), rate=1.0)
                protocol.delay(seconds=0.5)
                p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol + 80))), speed = 4.4)
                protocol.delay(seconds=0.5)
                p20.blow_out()
                p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + vol))))
                p20.move_to(dest.top())
                p20.drop_tip()
                p300.pick_up_tip()
            else:
                for i in range(2):
                    if i == 1:
                        p20.pick_up_tip()
                    p20.aspirate(vol/2, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol - i*(vol/2))), rate=0.25)
                    protocol.delay(seconds=1)
                    p20.move_to(eb_stock.top(), speed=10)
                    p20.dispense(vol/2, _well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i+1)*(vol/2)))), rate=1.0)
                    protocol.delay(seconds=0.5)
                    p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i+1)*(vol/2) + 80))), speed = 4.4)   #slowly +Z pipette, pulling droplet out of tip
                    protocol.delay(seconds=0.5)
                    p20.blow_out()                                                                  #blows bubble out tip
                    p20.move_to(_well_20.move(types.Point(z=getMagWellHeight(dest_vol + (i)*(vol/2)))))          #merges bubble with liquid surface
                    p20.move_to(dest.top())
                    p20.drop_tip()
            p20.pick_up_tip()
            p300.pick_up_tip()
        else:
            p300.pick_up_tip()
            for _ in range(1):
                p300.aspirate(vol, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol)))
                p300.dispense(vol, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol)))
            p300.aspirate(vol, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol - vol)), rate = 0.2)
            protocol.delay(seconds=1)
            p300.move_to(eb_stock.top(), speed=10)
            p300.dispense(vol, _well_300.move(types.Point(z=getMagWellHeight(dest_vol + vol))), rate=0.2)
            protocol.delay(seconds=1)
            p300.move_to(_well_300.move(types.Point(z=getMagWellHeight(dest_vol + vol + 80))), speed = 4.4)
            protocol.delay(seconds=1)
            p300.blow_out()
            p300.move_to(dest.top())
            
        print("current eb_stock: " + str(eb_stock_vol))
        eb_stock_vol = eb_stock_vol - vol*8
        print("subtracted eb_stock: " + str(eb_stock_vol))

    #size selection protocol for 96 ring magnet & biorad hard-shell plate
    def sel_96_ring_mag(
        well: protocol_api.labware.Well,
        cDNA: protocol_api.labware.Well,
        spri_vol: float,
        cDNA_vol: float,
        mix_vol: float,
        mix_rep: int,
        inc_sec: int,
        mag_sec: int,
        pel: bool,
        dry_sec: int,
        eb_vol: float,
        inc_sec_2: int,
        mag_sec_2: int,
        dest: protocol_api.labware.Well,
        dest_vol: float,
        dest_rep: int,
        _w = [], 
        multiplex = bool,
        mag_source = bool,
        to_mag = bool):

        #position adjustments have local scope so specific `dest` well is referenced
        _well_300_nomag = well.top().move(types.Point(
            x=well_300_nomag[0],
            y=well_300_nomag[1],
            z=well_300_nomag[2]))
        _well_300_mag = well.top().move(types.Point(
            x=well_300_mag[0],
            y=well_300_mag[1],
            z=well_300_mag[2]))

        #only use if dispensing to mag plate & immedietly call sel_96_ring_mag() on other part of size selection
        _dest_well_300_mag = dest.top().move(types.Point(
            x=well_300_mag[0],
            y=well_300_mag[1],
            z=well_300_mag[2]
        ))

        mag.disengage()
        
        p20.pick_up_tip()
        #allows cDNA already placed on mag when mag_source is true
        if not mag_source:
            p300.pick_up_tip()
            cDNA_transfer(
                source = cDNA,
                vol = cDNA_vol,
                dest = well,
                dest_vol = 0)

        p300.pick_up_tip(spri_tip)
        spri_stock_mix_transfer(
            vol = spri_vol,
            dest = well,
            dest_vol = cDNA_vol)

        for _ in range(mix_rep):
            p300.aspirate(mix_vol, _well_300_nomag.move(types.Point(z=0.5)))
            protocol.delay(seconds=0.5)
            p300.dispense(mix_vol, _well_300_nomag.move(types.Point(z=0.5)), rate=2)
            protocol.delay(seconds=0.5)
        p300.move_to(well.top())

        print("incubation starting: " + str(inc_sec))
        inc_start = time.monotonic()
        while time.monotonic() < inc_start + inc_sec:
            p300.aspirate(mix_vol - 20, _well_300_nomag, rate=0.1)
            p300.dispense(mix_vol - 20, _well_300_nomag, rate=0.1)
        print("incubation finished")

        p300.move_to(_well_300_nomag.move(types.Point(z=getMagWellHeight(spri_vol + cDNA_vol + 80))), speed=4.4)
        protocol.delay(seconds=1)
        p300.blow_out()
        p300.move_to(_well_300_nomag.move(types.Point(z=getMagWellHeight(spri_vol + cDNA_vol))))
        p300.move_to(well.top())
        
        print("magnet engaged")
        mag.engage(height=mag_z)
        p300.drop_tip()
        protocol.delay(seconds=mag_sec)

        #Post Mag Sep
        if pel:     #trash supernatent, wash pellet, resuspend pellet, incubate 2, then magnet 2
            p300.pick_up_tip()
            if multiplex:
                p300.aspirate(75, _well_300_mag, rate=0.2)
                protocol.delay(seconds=1)
                p300.move_to(_well_300_mag.move(types.Point(z=10)), speed = 2.5)
                p300.move_to(well.top())
                p300.dispense(75, mult_cleanup.bottom(z=1), rate=0.2)
            p300.aspirate(spri_vol + cDNA_vol + 10, _well_300_mag, rate=0.2)
            protocol.delay(seconds=1)
            p300.move_to(_well_300_mag.move(types.Point(z=10)), speed = 2.5)
            p300.move_to(well.top())
            p300.drop_tip()

            eth_wash_drain(
                    _eth_stock = getEthStock(),
                    _well = well,
                    _w = _w)

            print("dry_sec in 96s protocol has elapsed" + str(datetime.datetime.now()))
            protocol.delay(seconds=dry_sec-39)  #it takes 39 seconds to reach this point after ethanol is removed from pellet
            mag.disengage()
            eb_stock_transfer(
                vol = eb_vol,
                dest = well,
                dest_vol = 0)
            resusp_pel_mix_inc_mag(
                _mag_well = well,
                _mix_vol = eb_vol - 10,
                _tot_vol = eb_vol,
                _inc_sec = inc_sec_2,
                _mag_sec = mag_sec_2)
        
        #required regardless of pellet resuspension or not: transfers supernatent to specified location (likely temp block)
        #TODO: dispense at liquid level on temp block tubestrip

        if to_mag:
            if dest_rep == 8:
                p300.pick_up_tip()
                p300.aspirate(dest_rep*dest_vol, _well_300_mag, rate=0.2)
                protocol.delay(seconds=1)
                p300.move_to(_well_300_mag.move(types.Point(z=10)), speed = 1)
                p300.dispense(dest_rep*dest_vol, _dest_well_300_mag)
                protocol.delay(seconds=1)
                p300.move_to(dest.top(), speed = 1)
                p300.drop_tip()
                dest_rep = 1
            for i in range(dest_rep):
                vacuum_aspirate_transfer(
                    _asp_pos = _well_300_mag,
                    _asp_spd = 0.2,
                    _vol = dest_vol,
                    _dest = _dest_well_300_mag,
                    _blow_pos = dest.top(),
                    _reps = 1)
        else:
            if dest_rep == 8:
                p300.pick_up_tip()
                p300.aspirate(dest_rep*dest_vol, _well_300_mag, rate=0.2)
                protocol.delay(seconds=1)
                p300.move_to(_well_300_mag.move(types.Point(z=10)), speed = 1)
                p300.dispense(dest_rep*dest_vol, dest.bottom(z=1))
                p300.drop_tip()
                dest_rep = 1
            for i in range(dest_rep):
                vacuum_aspirate_transfer(
                    _asp_pos = _well_300_mag,
                    _asp_spd = 0.2,
                    _vol = dest_vol,
                    _dest = dest.bottom(),
                    _blow_pos = dest.top(),
                    _reps = 1)
        p20.drop_tip()
        mag.disengage() #magnet will be engaged if pel is True 
    ## END HELPER FUNCTIONS ##


    '''
    _well:              new magnet well to mix in
    _tc_dest:           TC well destination
    _amp_rxn_mix_stock: amp rxn mix stock on ice (prepped but not mixed)
    '''
    def dyn_cleanup_amplification(
        _well: protocol_api.labware.Well,
        _tc_dest: protocol_api.labware.Well,
        _amp_rxn_mix_stock: protocol_api.labware.Well):
        
        print("Load 90ul GEM sample in: " + str(_well))
        print("Add 125ul pink recovery agent to 90ul GEM sample in: " + str(_well))
        print("    wait 2 minutes for separation")
        print("        if sep incomplete:")
        print("            transfer to tubestrip extremely gently")
        print("            invert tubestrip 5x")
        print("            centrifuge briefly")
        print("            transfer back to: " + str(_well))
        print("Slowly remove 125ul recovery agent/artitioning oil (pink) from bottom of tube")
        print("    do not aspirate aqueous sample")
        input("press enter to continue...")

        #positions referencing specific _well
        _well_300_nomag = _well.top().move(types.Point(
            x=well_300_nomag[0],
            y=well_300_nomag[1],
            z=well_300_nomag[2]))
        _well_300_mag = _well.top().move(types.Point(
            x=well_300_mag[0],
            y=well_300_mag[1],
            z=well_300_mag[2]))

        mag.disengage()
        p300.pick_up_tip()
        p20.pick_up_tip()
        p300.mix(30, 180, dyn_stock, rate=2.0)
        p300.aspirate(200, dyn_stock, rate=0.2)
        protocol.delay(seconds=4)
        p300.move_to(dyn_stock.top())
        protocol.delay(seconds=4)
        p300.touch_tip()
        p300.dispense(200, _well.top(), rate=0.2)
        protocol.delay(seconds=1)
        inc_sec = 600
        print("dynabead incubation starting: " + str(inc_sec) + " seconds")
        inc_start = time.monotonic()
        while time.monotonic() < inc_start + inc_sec:
            p300.aspirate(200, _well_300_mag)
            p300.dispense(200, _well_300_mag)
        print(datetime.datetime.now())
        p300.move_to(_well.top(z=4), speed = 4.4)
        mag.engage(height=mag_z)
        protocol.delay(seconds=20)
        p300.blow_out()
        protocol.delay(seconds=220)
        for _ in range(2):
            p300.aspirate(200, _well_300_mag, rate=0.2)
            p300.move_to(_well_300_mag.move(types.Point(z=2)), speed=1)
            p300.dispense(200, protocol.fixed_trash['A1'])
        p300.drop_tip()
        
        eth_wash_drain(getEthStock(), _well, _w=[260,250])

        protocol.delay(seconds=30)  #exactly 1-minute after ethanol is removed from pellet (10x protocol)

        mag.disengage()

        vol = 36
        for i in range(2):
            p20.aspirate(vol/2, elu_sol_1.bottom(z=getEppendorf_1_5Height(elu_stock_vol - i*(vol/2))), rate=1)
            p20.dispense(vol/2, _well_300_nomag.move(types.Point(z=getMagWellHeight((i+1)*(vol/2)))), rate=1)
            p20.move_to(_well_300_nomag.move(types.Point(z=getMagWellHeight((i+1)*(vol/2) + 40))), speed = 4.4)   #slowly +Z pipette, pulling droplet out of tip
            p20.blow_out()                                                                      #blows bubble out tip
            p20.move_to(_well.top())
        p300.pick_up_tip()

        inc_sec_elu = 140
        print("elu_sol_1 incubation starting: " + str(inc_sec_elu) + " seconds")
        inc_start_elu = time.monotonic()
        while time.monotonic() < inc_start_elu + inc_sec_elu:
            p300.aspirate(30, _well_300_nomag.move(types.Point(z=-0.5)), rate=2)
            p300.move_to(_well_300_nomag.move(types.Point(z=0.5)), speed=1)
            p300.dispense(30, _well_300_nomag.move(types.Point(z=0.5)), rate=2)
            protocol.delay(seconds=0.5)
        print(datetime.datetime.now())
        protocol.delay(seconds=1)
        p300.move_to(_well_300_nomag.move(types.Point(z=getMagWellHeight(35 + 80))), speed=2)
        protocol.delay(seconds=1)
        p300.blow_out()
        p300.drop_tip()
        mag.engage(height=mag_z)

        #lid open takes between 28 and 4 seconds, plenty of time for mag sep in small volume
        tc.open_lid()

        #amp_mix_into_tc
        p300.pick_up_tip()
        for _ in range(30):
            p300.aspirate(40, _amp_rxn_mix_stock.bottom(z=0.5))
            p300.dispense(40, _amp_rxn_mix_stock.bottom(z=0.5))
        p300.aspirate(65, _amp_rxn_mix_stock.bottom(z=0.5), rate = 0.2)
        protocol.delay(seconds=0.5)
        p300.move_to(_amp_rxn_mix_stock.bottom(z=2), speed=1)
        p300.dispense(65, _tc_dest.bottom(z=1), rate=0.2)
        protocol.delay(seconds=0.5)
        p300.move_to(_tc_dest.bottom(z=10), speed = 1)
        p300.move_to(_tc_dest.top())
        p300.blow_out()
        p300.drop_tip()
        p300.pick_up_tip()

        #duration: 1:06
        _sup_vol = 17.5
        _sup_rep = 2
        #transfer supernatent (_well must be magnet well)
        vacuum_aspirate_transfer(
            _asp_pos=_well_300_mag,
            _asp_spd=0.2,
            _vol=_sup_vol,
            _dest=_tc_dest.bottom(),
            _blow_pos=_tc_dest.top(),
            _reps=_sup_rep)
        mag.disengage()
        p20.drop_tip()

        p300.aspirate(65, _tc_dest.bottom(z=1))
        for i in range(30):
            p300.dispense(60, _tc_dest)
            p300.aspirate(60, _tc_dest.bottom(z=1))
        p300.dispense(65, _tc_dest.bottom(z=1))

        p300.move_to(_tc_dest.top())
        protocol.delay(seconds=1)
        p300.blow_out()
        p300.drop_tip()

        #start: 58:54
        cdna_amp_pcr_loop_prof = [
            {"temperature": 98, "hold_time_seconds": 15},
            {"temperature": 63, "hold_time_seconds": 20},
            {"temperature": 72, "hold_time_seconds": 60}
        ] #11 cycles if sampling large number of cells, 12 cycles if small (<12,000 targeted cell recov. per GEM well)
        
        tc.close_lid()
        print("bringing lid to temp: " + str(datetime.datetime.now()))
        tc.set_lid_temperature(105)
        print("block temp: " + str(datetime.datetime.now()))
        tc.set_block_temperature(98, hold_time_minutes=3, block_max_volume=100)
        print("looping: " + str(datetime.datetime.now()))
        tc.execute_profile(steps= cdna_amp_pcr_loop_prof, repetitions=12, block_max_volume=100)
        print("pcr: " + str(datetime.datetime.now()))
        tc.set_block_temperature(72, hold_time_seconds=60, block_max_volume=100)
        print("pcr done, cooling: " + str(datetime.datetime.now()))
        tc.set_block_temperature(4)
        print("opening lid: " + str(datetime.datetime.now()))
        tc.open_lid()
        #end: 1:42:28
        #iteration_8 duration: 44:34



    '''
    _tc_source:     _tc_dest of dyn_cleanup_amplification
    _well:          new magnet well to mix in
    _purified_cDNA: destination on temp plate for final product of 2.3A
    ''' 
    def cDNA_cleanup_pellet_cleanup(
        _tc_source: protocol_api.labware.Well,
        _well: protocol_api.labware.Well,
        _purified_cDNA: protocol_api.labware.Well,
        _multiplex: bool):

        sel_96_ring_mag(
            well = _well,
            cDNA = _tc_source,
            spri_vol = 60,
            cDNA_vol = 100,
            mix_vol = 130, 
            mix_rep = 30,
            inc_sec = 300,
            mag_sec = 240,
            pel = True,
            dry_sec = 120,
            eb_vol = 41,
            inc_sec_2 = 120,
            mag_sec_2 = 120,
            dest = _purified_cDNA,
            dest_vol = 20,
            dest_rep = 2,
            _w = [200,200],
            multiplex = _multiplex,
            mag_source = False,
            to_mag = True
        )

        if _multiplex:
            sel_96_ring_mag(
                well = mult_cleanup,
                cDNA = mult_cleanup,
                spri_vol = 70,
                cDNA_vol = 75,
                mix_vol = 130, 
                mix_rep = 30,
                inc_sec = 300,
                mag_sec = 300,
                pel = True,
                dry_sec = 120,
                eb_vol = 41,
                inc_sec_2 = 120,
                mag_sec_2 = 120,
                dest = multiplex_cln,
                dest_vol = 20,
                dest_rep = 2,
                _w = [230,230],
                multiplex = False,
                mag_source = True,
                to_mag = False,
            )

    '''
    _frag_mix is frag buffer & enzyme added to same well on temp plate @4C (tranferred to TC, then mixed)
    _frag_mix_tc is destination for cDNA mix on TC plate
    _purified_cDNA is destination on temp plate for final product of 2.3A
    EB buffer stock
    _treated_cDNA is magnet well for post-tc _frag_mix_tc solution
    _size_sel_0_cDNA is _treated_cDNA, after one round of SPRIselect
    _ada_lig_mix is final destination of _size_sel_cDNA for ada_lig_cleanup next step (temp plate)
                 is already prepped on ice with lig buffer, dna ligase, and ada oligo (unmixed)
    '''
    def frag_end_repair_a_tailing_size_sel(
        _frag_mix: protocol_api.labware.Well,
        _frag_mix_tc: protocol_api.labware.Well,
        _purified_cDNA: protocol_api.labware.Well,
        _treated_cDNA: protocol_api.labware.Well,
        _size_sel_0_cDNA: protocol_api.labware.Well):

        #tc already pre-cooled, open from dyn_cleanup_amplification
        print("pre-cooling tc block to 4C if not already pre-cooled: " + str(datetime.datetime.now()))
        tc.set_block_temperature(4)
        print("opening lid: " + str(datetime.datetime.now()))
        tc.open_lid()

        p20.pick_up_tip()
        p20.aspirate(15, eb_stock.bottom(z=getEppendorf_1_5Height(eb_stock_vol - 15)), rate=0.25)
        protocol.delay(seconds=1)
        p20.move_to(eb_stock.top(), speed=10)
        p20.dispense(15, _frag_mix_tc.bottom(z=0.2), rate=1.0)
        protocol.delay(seconds=0.5)
        p20.move_to(_frag_mix_tc.bottom(z=4), speed = 4.4)
        protocol.delay(seconds=0.5)
        p20.move_to(_frag_mix_tc.top())
        p20.blow_out()
        p20.touch_tip()
        p20.drop_tip()

        p20.pick_up_tip()
        for _ in range(15):
            p20.aspirate(14, _frag_mix.bottom(z=0.1))
            p20.dispense(14, _frag_mix.bottom(z=0.1))
        vacuum_aspirate_transfer(
            _asp_pos=_frag_mix.bottom(z=0.1),
            _asp_spd=0.2,
            _vol=15,
            _dest=_frag_mix_tc,
            _blow_pos=_frag_mix_tc.top(),
            _reps=1)
        p20.touch_tip()
        p20.touch_tip()
        p20.drop_tip()
        p20.pick_up_tip()
        vacuum_aspirate_transfer(
            _asp_pos=_purified_cDNA.bottom(z=0.2),
            _asp_spd=0.2,
            _vol=20,
            _dest=_frag_mix_tc,
            _blow_pos=_frag_mix_tc.top(),
            _reps=1)
        p20.blow_out(_frag_mix_tc)
        p20.touch_tip()
        p20.touch_tip()
        p20.drop_tip()

        p300.pick_up_tip()
        for _ in range(30):
            p300.aspirate(30, _frag_mix_tc.bottom(0.2))
            p300.dispense(30, _frag_mix_tc.bottom(0.2))
        p300.move_to(_frag_mix_tc.top())
        protocol.delay(seconds=4)
        p300.blow_out(_frag_mix_tc.top())
        p300.touch_tip()
        p300.drop_tip()
        
        #iteration_8 start: 2:14:00
        print("bringing lid to temp: " + str(datetime.datetime.now()))
        tc.set_lid_temperature(65)
        print("closing lid: " + str(datetime.datetime.now()))
        tc.close_lid()
        print("starting fragmentation, 5min: " + str(datetime.datetime.now()))
        tc.set_block_temperature(32, hold_time_minutes=5, block_max_volume=50)
        print("starting end repair, a-tailing. 30min: " + str(datetime.datetime.now()))
        tc.set_block_temperature(65, hold_time_minutes=30, block_max_volume=50)
        print("done, starting to cool block: " + str(datetime.datetime.now()))
        tc.set_block_temperature(4)
        #3:03:20  
        print("opening lid: " + str(datetime.datetime.now()))
        tc.open_lid()
        #3:04:08 
        print("pre-cooling lid for next step: " + str(datetime.datetime.now()))
        tc.set_lid_temperature(37)
        #iteration_8 end: 3:31:00  30 minute lid temp change????!!?

        sel_96_ring_mag(
            well = _treated_cDNA,
            cDNA = _frag_mix_tc,
            spri_vol = 30,
            cDNA_vol = 50,
            mix_vol = 50,
            mix_rep = 30,
            inc_sec = 300,
            mag_sec = 240,
            pel = False,
            dry_sec = 0,
            eb_vol = 0,
            inc_sec_2 = 0,
            mag_sec_2 = 0,
            dest = size_sel_0_cDNA,
            dest_vol = 18.75,
            dest_rep = 4,
            _w = [0,0],
            multiplex = False,
            mag_source = False,
            to_mag = True
        )

        sel_96_ring_mag(
            well = _size_sel_0_cDNA,
            cDNA = size_sel_0_cDNA,
            spri_vol = 10,
            cDNA_vol = 75,
            mix_vol = 55,
            mix_rep = 30,
            inc_sec = 300,
            mag_sec = 240,
            pel = True,
            dry_sec = 60,
            eb_vol = 51,
            inc_sec_2 = 120,
            mag_sec_2 = 120,
            dest = ada_lig_mix,
            dest_vol = 16.67,
            dest_rep = 3,
            _w = [125,125],
            multiplex = False,
            mag_source = True,
            to_mag = False
        )
    
    '''
    _ada_lig_mix is 50ul final product of previous frag_end_repair_a_tailing_size_sel step
                    50ul adaptor ligation mix (unmixed) prepared within well previous step
    _ada_lig_mix_tc is tc destination for mixed 100ul _ada_lig_mix, prev step product
    '''
    def ada_lig_cleanup(
        _ada_lig_mix: protocol_api.labware.Well,
        _ada_lig_mix_tc: protocol_api.labware.Well):

        print("bringing block to 20C")
        tc.set_block_temperature(20)
        p300.pick_up_tip()
        for _ in range(30):
            p300.aspirate(70, _ada_lig_mix.bottom(z=0.3))
            p300.dispense(70, _ada_lig_mix.bottom(z=0.3))
        p300.aspirate(90, _ada_lig_mix.bottom(z=0.3))
        p300.dispense(90, _ada_lig_mix.bottom(z=0.3))
        p300.aspirate(90, _ada_lig_mix.bottom(z=0.3), rate=0.2)
        protocol.delay(seconds=1)
        p300.move_to(_ada_lig_mix.bottom(z=2), speed=1)
        p300.move_to(_ada_lig_mix.top())
        p300.dispense(90, _ada_lig_mix_tc.bottom(z=0.3))
        p300.move_to(_ada_lig_mix_tc.top())
        protocol.delay(seconds=4)
        p300.blow_out(_ada_lig_mix_tc.top())
        p300.touch_tip()
        p300.drop_tip()
        p20.pick_up_tip()
        #fetch remaining 10ul, + extra volume if accuracy is not perfect
        vacuum_aspirate_transfer(
            _asp_pos=_ada_lig_mix.bottom(),
            _asp_spd=1.0,
            _vol=16.67,
            _dest=_ada_lig_mix_tc.top(z=-2),    #TODO: dispense just above liquid height to avoid bubbles
            _blow_pos=_ada_lig_mix_tc.top(),
            _reps=1)
        p20.drop_tip()
        print("closing lid: " + str(datetime.datetime.now()))
        tc.close_lid()
        print("bringing lid to temp: " + str(datetime.datetime.now()))
        tc.set_lid_temperature(37)
        print("20c for 15min: " + str(datetime.datetime.now()))
        tc.set_block_temperature(20, hold_time_minutes=15, block_max_volume=100)
        print("incubate done, cooling: " + str(datetime.datetime.now()))
        tc.set_block_temperature(4)
        print("opening lid: " + str(datetime.datetime.now()))
        tc.open_lid()

        sel_96_ring_mag(
            well = lig_cleanup_0,
            cDNA = _ada_lig_mix_tc,
            spri_vol = 80,
            cDNA_vol = 100,
            mix_vol = 140, 
            mix_rep = 30,
            inc_sec = 300,
            mag_sec = 240,
            pel = True,
            dry_sec = 120,
            eb_vol = 31,
            inc_sec_2 = 120,
            mag_sec_2 = 120,
            dest = postlig_cleanup,
            dest_vol = 15,
            dest_rep = 2,
            _w = [200,200],
            multiplex = False,
            mag_source = False,
            to_mag = False
        )

    '''
    _samp_index_pcr is tc location of final product from previous step
                    is not yet mixed with Amp mix or dual index TT set A
    _amp_mix is >=50ul amp mix stock on temp plate
    _dual_ind_tt_set_a is pre-aliquotted onto temp plate
    '''
    def index_pcr_size_sel(
        _samp_index_pcr: protocol_api.labware.Well,
        _dual_ind_tt_set_a: protocol_api.labware.Well):

        
        p20.pick_up_tip()
        #TODO: centralize Amp mix location on temp block, use for amp_rxn_mix prep
        vacuum_aspirate_transfer(
            _asp_pos=postlig_cleanup.bottom(z=0.1),
            _asp_spd=0.2,
            _vol=15,
            _dest=_samp_index_pcr,
            _blow_pos=_samp_index_pcr.top(),
            _reps=2)
        vacuum_aspirate_transfer(
            _asp_pos=amp_mix.bottom(z=0.1),
            _asp_spd=0.2,
            _vol=16.67,
            _dest=_samp_index_pcr,
            _blow_pos=_samp_index_pcr.top(),
            _reps=3)
        vacuum_aspirate_transfer(
            _asp_pos = _dual_ind_tt_set_a.bottom(z=0.1),
            _asp_spd = 0.2,
            _vol=20,
            _dest=_samp_index_pcr,
            _blow_pos=samp_index_pcr.top(),
            _reps=1)
        p20.drop_tip()
        p300.pick_up_tip()
        for _ in range(10):
            p300.aspirate(70, _samp_index_pcr.bottom(z=0.3))
            p300.dispense(70, _samp_index_pcr.bottom(z=0.3))
        p300.move_to(_samp_index_pcr.top())
        protocol.delay(seconds=4)
        p300.touch_tip()
        p300.blow_out(_samp_index_pcr)
        p300.touch_tip()
        p300.drop_tip()
        print("bringing block to 20: " + str(datetime.datetime.now()))
        tc.set_block_temperature(20)
        print("bringing lid to 105: " + str(datetime.datetime.now()))
        tc.set_lid_temperature(105)
        print("closing lid: " + str(datetime.datetime.now()))
        
        tc.close_lid()

        with open('thermo-cycles-3.5.json') as cycle_file:
            json_def = json.load(cycle_file)
            _cycles = int(json_def["num-cycles"])

        if _cycles == 0:
            while True:
                print("3.5: begining automated PCR steps. Please input # of cycles calculated from cDNA input from 2.4QC")
                _in = input("total cycles: ")
                _cycles = int(float(_in))
                if _cycles >= 5 and _cycles <=20:
                   break
                else:
                    print("invalid input")

        #sample index PCR
        amp_ind_pcr_loop_prof = [
            {'temperature': 98, 'hold_time_seconds': 20},
            {'temperature': 54, 'hold_time_seconds': 30},
            {'temperature': 72, 'hold_time_seconds': 20}
        ]
        #iteration_8 start: 44:15
        print("bringing block to temp: " + str(datetime.datetime.now()))
        tc.set_block_temperature(98, hold_time_seconds=45, block_max_volume=100)
        print("entering loop for " + str(_cycles) + "~70sec reps: " + str(datetime.datetime.now()))
        tc.execute_profile(steps= amp_ind_pcr_loop_prof, repetitions=_cycles, block_max_volume=100)
        print("bringing block to temp: " + str(datetime.datetime.now()))
        tc.set_block_temperature(72, hold_time_seconds=60, block_max_volume=100)
        print("done, cooling block to 4: " + str(datetime.datetime.now()))
        tc.set_block_temperature(4)
        print("opening lid: " + str(datetime.datetime.now()))
        tc.open_lid()
        #iteration_8 end: 1:27:23

        sel_96_ring_mag(
            well = indexed_cDNA,
            cDNA = samp_index_pcr,
            spri_vol = 60,
            cDNA_vol = 100,
            mix_vol = 120,
            mix_rep = 30,
            inc_sec = 300,
            mag_sec = 240,
            pel = False,
            dry_sec = 0,
            eb_vol = 0,
            inc_sec_2 = 0,
            mag_sec_2 = 0,
            dest = size_sel_0_ind_cDNA,
            dest_vol = 18.75,
            dest_rep = 8,
            _w = [0,0],
            multiplex = False,
            mag_source = False,
            to_mag = True
        )

        sel_96_ring_mag(
            well = size_sel_0_ind_cDNA,
            cDNA = size_sel_0_ind_cDNA,
            spri_vol = 20,
            cDNA_vol = 150,
            mix_vol = 150,
            mix_rep = 60,
            inc_sec = 300,
            mag_sec = 240,
            pel = True,
            dry_sec = 39,
            eb_vol = 36,
            inc_sec_2 = 120,
            mag_sec_2 = 120,
            dest = final_product,
            dest_vol = 18,
            dest_rep = 2,
            _w = [200,200],
            multiplex = False,
            mag_source = True,
            to_mag = False
        )

    def multiplex_index_pcr_size_sel():

        p20.pick_up_tip()
        #TODO: centralize Amp mix location on temp block, use for amp_rxn_mix prep
        vacuum_aspirate_transfer(
            _asp_pos=multiplex_cln.bottom(z=0.1),
            _asp_spd=0.2,
            _vol=10,
            _dest=mult_index_pcr,
            _blow_pos=mult_index_pcr.top(),
            _reps=1)
        vacuum_aspirate_transfer(
            _asp_pos=multiplex_ind_pcr.bottom(z=0.1),
            _asp_spd=0.2,
            _vol=17.5,
            _dest=mult_index_pcr,
            _blow_pos=mult_index_pcr.top(),
            _reps=4)
        vacuum_aspirate_transfer(
            _asp_pos = dual_ind_nn_set_a.bottom(z=0.1),
            _asp_spd = 0.2,
            _vol=20,
            _dest=mult_index_pcr,
            _blow_pos=mult_index_pcr.top(),
            _reps=1)
        p20.drop_tip()
        p300.pick_up_tip()
        for _ in range(10):
            p300.aspirate(80, mult_index_pcr.bottom(z=0.3))
            p300.dispense(80, mult_index_pcr.bottom(z=0.3))
        p300.move_to(mult_index_pcr.top())
        protocol.delay(seconds=4)
        p300.touch_tip()
        p300.blow_out(mult_index_pcr)
        p300.touch_tip()
        p300.drop_tip()
        print("bringing block to 20: " + str(datetime.datetime.now()))
        tc.set_block_temperature(20)
        print("bringing lid to 105: " + str(datetime.datetime.now()))
        tc.set_lid_temperature(105)
        print("closing lid: " + str(datetime.datetime.now()))
        tc.close_lid()

        #multiplex index PCR
        amp_multi_index_pcr_loop_prof = [
            {'temperature': 98, 'hold_time_seconds': 20},
            {'temperature': 54, 'hold_time_seconds': 30},
            {'temperature': 72, 'hold_time_seconds': 20}
        ]
        
        print("bringing block to temp: " + str(datetime.datetime.now()))
        tc.set_block_temperature(98, hold_time_seconds=45, block_max_volume=100)
        print("entering loop for 6 ~70sec reps: " + str(datetime.datetime.now()))
        tc.execute_profile(steps= amp_multi_index_pcr_loop_prof, repetitions=6, block_max_volume=100)
        print("bringing block to temp: " + str(datetime.datetime.now()))
        tc.set_block_temperature(72, hold_time_seconds=60, block_max_volume=100)
        print("done, cooling block to 4: " + str(datetime.datetime.now()))
        tc.set_block_temperature(4)
        print("opening lid: " + str(datetime.datetime.now()))
        tc.open_lid()

        sel_96_ring_mag(
            well = mult_size_sel,
            cDNA = mult_index_pcr,
            spri_vol = 120,
            cDNA_vol = 100,
            mix_vol = 150,
            mix_rep = 60,
            inc_sec = 300,
            mag_sec = 360,
            pel = True,
            dry_sec = 120,
            eb_vol = 41,
            inc_sec_2 = 120,
            mag_sec_2 = 120,
            dest = multiplex_fin,
            dest_vol = 20,
            dest_rep = 2,
            _w = [260,260],
            multiplex = False,
            mag_source = False,
            to_mag = False
        )

    ## STONKS ##
    #TODO: remove tip height adjustment for these stock well
    spri_stock  = r15['A3']
    eb_stock    = r15['A4']
    elu_sol_1   = r15['A5']
    dyn_stock   = r15['A6']
    eth_stock   = r15['A8']     #10000ul ethanol
    eth2_stock  = r15['A9']     #10000ul ethanol
    eth3_stock  = r15['A10']    #10000ul ethanol
    
    ## WELLS ##
    dyn_cleanup         = mag_plate['A12']
    cDNA_cleanup        = mag_plate['A11']
    treated_cDNA        = mag_plate['A10']  #3.2 size sel 0            
    size_sel_0_cDNA     = mag_plate['A9']   #3.2 size sel 1
    lig_cleanup_0       = mag_plate['A8']   #3.4 lig cleanup
    indexed_cDNA        = mag_plate['A7']   #3.6 size sel 0
    size_sel_0_ind_cDNA = mag_plate['A6']   #3.6 size sel 1
    mult_cleanup        = mag_plate['A5']
    mult_size_sel       = mag_plate['A4']
 
    cDNA_amp_tc         = tc_plate['A5']
    frag_mix_tc         = tc_plate['A6']
    ada_lig_mix_tc      = tc_plate['A7']
    samp_index_pcr      = tc_plate['A8']
    mult_index_pcr      = tc_plate['A9']

    ## COLD SAMPLES ##
    postlig_cleanup     = temp_plate['A8']
    multiplex_cln       = temp_plate['A9']  #3
    purified_cDNA       = temp_plate['A10'] #3
    final_product       = temp_plate['A11'] #3
    multiplex_fin       = temp_plate['A12'] #3

    # 4C STOCKS #
    amp_rxn_mix         = temp_plate['A1']      #  55ul amp mix                     [1x+10%]
                                                #  16.5ul feature cDNA Primers 3    [1x+10%]            
    frag_mix            = temp_plate['A2']      #   5ul frag buffer     [unmixed]
                                                #  10ul frag enzyme
    ada_lig_mix         = temp_plate['A3']      #  20ul ligation buffer [unmixed]
                                                #  10ul DNA ligase
                                                #  20ul ada oligos 
    amp_mix             = temp_plate['A4']      #  50ul amp mix
    dual_ind_tt_set_a   = temp_plate['A5']      #  20ul dual index tt set a  [RECORD INDEX USED]
    #if multiplexing:
    multiplex = True
    dual_ind_nn_set_a   = temp_plate['A6']      #  20ul dual index nn set a  [RECORD INDEX USED]
    multiplex_ind_pcr   = temp_plate['A7']      #  50ul amp mix
                                                #  20ul eb

    ## RE-USED TIPS ##
    spri_tip = t300_0['A1']
    

    #| tc |t300|
    #| tc |t300|temp|
    #|magm|t300|resv|
    #| t20| t20|t300|


    #temp:
    #|amp_rxn_mix|frag_mix|ada_lig_mix|amp_mix|dual_ind_tt_set_a|dual_ind_nn_set_a|multiplex_ind_pcr|postlig_cleanup|multiplex_cln|multiplex_fin|purified_cDNA|final_product|

    #resv:
    #|spri| eb | eth|    |    |    |    |    |    |    |    |    |

    
    
    ## REAGENTS NEEDED, OPEN ##
    print("reagents are open...")

    #est: 0h:49m
    input("press enter to proceed to: dyn_cleanup_amplification")
    #dyn_cleanup_amplification(
    #    _well               = dyn_cleanup,
    #    _tc_dest            = cDNA_amp_tc,
    #    _amp_rxn_mix_stock  = amp_rxn_mix)
    
    #est: 0h:17m
    #input("press enter to proceed to: cDNA_cleanup_pellet_cleanup")
    #cDNA_cleanup_pellet_cleanup(
    #    _tc_source          = cDNA_amp_tc,
    #    _well               = cDNA_cleanup,
    #    _purified_cDNA      = purified_cDNA,
    #    _multiplex          = multiplex)
    
    #est: 1h:11m
    print("prepare step 3 reagents, place at proper locations on temp block")
    print("refill ethanol")
    print("replace tips: " + str(t300_0) + str(t300_1))
    input("press enter to proceed to: frag_end_repair_a_tailing_size_sel")
    p300.reset_tipracks()
    p300.starting_tip=t300_0['A2']        #accomidates SPRIselect mixing tip reuse 
    frag_end_repair_a_tailing_size_sel(
        _frag_mix           = frag_mix,
        _frag_mix_tc        = frag_mix_tc,
        _purified_cDNA      = purified_cDNA,
        _treated_cDNA       = treated_cDNA,
        _size_sel_0_cDNA    = size_sel_0_cDNA)
    
    #est: 0h:45m 
    #input("press enter to proceed to: ada_lig_cleanup")
    ada_lig_cleanup(
        _ada_lig_mix        = ada_lig_mix,
        _ada_lig_mix_tc     = ada_lig_mix_tc)

    #est: 0h:53m
    #input("press enter to proceed to: index_pcr_size_sel")
    index_pcr_size_sel(
        _samp_index_pcr     = samp_index_pcr,
        _dual_ind_tt_set_a     = dual_ind_tt_set_a)
    
    if multiplex:
        multiplex_index_pcr_size_sel()

run(protocol)