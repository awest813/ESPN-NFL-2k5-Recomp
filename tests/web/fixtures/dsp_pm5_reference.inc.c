/*
 * DSP56300 emulator
 *
 * Copyright (c) 2015 espes
 * Copyright (c) 2020-2025 Matt Borgerson
 *
 * Adapted from Hatari DSP M56001 emulation
 * (C) 2003-2008 ARAnyM developer team
 * Adaption to Hatari (C) 2008 by Thomas Huth
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; either version 2 of the License, or
 * (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
 */

/* Independent pre-specialization parallel-move reference. */
static void reference_pm_5(dsp_core_t* dsp)
{
    uint32_t memspace, numreg, value, xy_addr, retour;
/*
    01dd 0ddd w0aa aaaa             x:aa,D
                        S,x:aa
    01dd 0ddd w1mm mrrr             x:ea,D
                        S,x:ea
                        #xxxxxx,D
    01dd 1ddd w0aa aaaa             y:aa,D
                        S,y:aa
    01dd 1ddd w1mm mrrr             y:ea,D
                        S,y:ea
                        #xxxxxx,D
*/

    value = (dsp->cur_inst>>8) & BITMASK(6);

    if (dsp->cur_inst & (1<<14)) {
        retour = emu_calc_ea(dsp, value, &xy_addr);
    } else {
        xy_addr = value;
        retour = 0;
    }

    memspace = (dsp->cur_inst>>19) & 1;
    numreg = (dsp->cur_inst>>16) & BITMASK(3);
    numreg |= (dsp->cur_inst>>17) & (BITMASK(2)<<3);

    if (dsp->cur_inst & (1<<15)) {
        /* Write D */
        if (retour)
            value = xy_addr;
        else
            value = dsp56k_read_memory(dsp, memspace, xy_addr);
    }
    else {
        /* Read S */
        if ((numreg==DSP_REG_A) || (numreg==DSP_REG_B))
            emu_pm_read_accu24(dsp, numreg, &value);
        else
            value = dsp->registers[numreg];
    }


    /* Execute parallel instruction */
    opcodes_alu[dsp->cur_inst & BITMASK(8)](dsp);

    if (dsp->cur_inst & (1<<15)) {
        /* Write D */
        if (numreg == DSP_REG_A) {
            dsp->registers[DSP_REG_A0] = 0x0;
            dsp->registers[DSP_REG_A1] = value;
            dsp->registers[DSP_REG_A2] = value & (1<<23) ? 0xff : 0x0;
        }
        else if (numreg == DSP_REG_B) {
            dsp->registers[DSP_REG_B0] = 0x0;
            dsp->registers[DSP_REG_B1] = value;
            dsp->registers[DSP_REG_B2] = value & (1<<23) ? 0xff : 0x0;
        }
        else {
            dsp->registers[numreg] = value & BITMASK(registers_mask[numreg]);
        }
    }
    else {
        /* Read S */
        dsp56k_write_memory(dsp, memspace, xy_addr, value);
    }
}

