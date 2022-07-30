# Opentrons OT-2 10x Genomics single cell RNA sequencing library prep (with multiplexing!)

Manual single cell library preps are tedious and error-prone. Automated solutions are expensive up-front. This repo contains all code & hardware required to automate 10x Genomics library preps on the Opentrons platform for $26k.

<img src="https://github.com/retrobiosciences/opentrons-10x/blob/main/homebrew-connect.jpeg" alt="homebrew connect" width="200px">

### Protocol:

Prepping 8 libraries involves 2 hours of human labor[^1]. 

Step 1: GEM Generation & Barcoding is performed manually using [an automated pump](https://www.10xgenomics.com/instruments/chromium-controller)
Step 2:  (1:30)
- Pipette GEMs into PCR plate, add pink separation agent, wait 2 minutes, remove separation agent
- Load reagents, plates, and labware
- Begin automated portion
- Return within 24 hours to begin Step 3
Step 3: (4:30-5:00)
- If multiplexing:
	- reload pipette tips
- Begin automated portion
- Quantify DNA [^2]
	- update json file with appropriate PCR cycle count
- Collect prepped sample within 24 hours of completion (held at 4C in PCR plate indefinitely)
Send sample off for sequencing

---

### Required modifications:
Opentrons 96-ring Magnet Module

### Modules:
- Thermocycler Module
- Magnetic Module
- Temperature Module

### Labware:
- 96-well aluminum block
- Bio-Rad Hard-Shell 96-Well PCR Plate, high profile, semi skirted #HSS9601 (2x)
- NEST 0.1ul PCR plate full-skirt
- Opentrons 300ul Tips (4-6x)
- Opentrons 20ul Tips (2-3x)
- 12-well reagent trough

### Pipettes:
- P300 8-channel
- P20 8-channel

### Reagents:
- [10x 3' medium throughput v3.1](https://www.10xgenomics.com/support/single-cell-gene-expression/documentation/steps/library-prep/chromium-next-gem-single-cell-3-v-3-1-dual-index-libraries)

### Optional:
- Pipette cam (logs potential liquid transfer errors)[^3]

### Deck Setup:
opentrons | deck | setup
--- | --- | ---
10: thermocycler| 11: P300 tips| trash
7: thermocycler| 8: P300 tips | 9: P20 tips
4: mag module | 5: P300 tips | 6: P20 tips
1: temp module | 2: P300 tips | 3: 12-well trough

### Economic Efficiency:
 platform | hardware cost | servicing contract | throughput 
 --- | --- | --- | ---
 10x Chromium Connect | $260k | yes | 24-samples/day
 Opentrons| $26k | no | 32-samples/day
 
### Library prep quality:
bioanalyzer trace for step 2, step 3

sequencing results

[^1]: Automated reagent prep reduces manual work to 30 mins :). Running 8 robots continuously for a year, a company can reasonably expect to spend $70 million in reagents and prepare 70k sc-RNA seq samples (300M-1.4B cells).
[^2]: Skipping quantification step for samples with similar cDNA recovery allows completion of step 2 & 3 uninterrupted. Works great most of the time! Multiplexing uses too many P300 tips for this to work. P300 tip usage can be reduced, possibly eliminating this constraint
[^3]: I want to control the pipette with camera input. So much closed-loop precision at our fingertips!





# Opentrons 96-well magnet modification

Protocols involving SPRIselect and AMPure bead size selection perform poorly on the OT-2 robot. 
- Pipette positioning within well has low precision:
	- Ethanol washing directly onto pellet is difficult
	- Tips frequently scrape beads, reducing size selection specificity & yield
	- Aspirating supernatant from exactly bottom of well yields inconsistent results:
		- pipette forms seal with bottom of well
		- pipette fails to aspirate all supernatant

This repo contains all hardware required to modify the stock Opentrons Magnetic Module (side-pellet) with the spring-loaded [Alpaqua 96S Super Magnet](https://www.alpaqua.com/product/96s-super-magnet/) plate. 

