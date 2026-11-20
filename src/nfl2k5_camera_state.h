#ifndef NFL2K5_CAMERA_STATE_H
#define NFL2K5_CAMERA_STATE_H
#include <stdint.h>

/* The retail mode stack stores descriptors at object + depth*8 and its
 * current depth at +0x100 (sub_0006E390 / sub_0006E400). */
#define NFL2K5_CAMERA_FSM 0x00A84B18u
#define NFL2K5_CAMERA_FSM_DEPTH (NFL2K5_CAMERA_FSM + 0x100u)
#define NFL2K5_CAMERA_FSM_LIMIT 32u

static inline int nfl2k5_camera_mode_allows_match(uint32_t descriptor)
{
    /* These are full-screen UI states. Clock/team globals can survive an
     * attract demo or match, so their validity alone cannot identify a view.
     * Keep dual-purpose training and unknown world states on the
     * existing camera validation path. Only inspect the visible top mode. */
    switch (descriptor) {
    case 0:
    case 0x00515660u: /* Main Menu */
    case 0x005015CCu: /* Game Modes */
    case 0x00529AE0u: /* Anniversary catalog */
    case 0x00529D48u: /* Anniversary objective */
    case 0x0052728Cu: /* Team Select */
    case 0x00526948u: /* Team Select (alternate) */
    case 0x00585474u: /* Coach Match Up */
    case 0x00585048u: /* V.I.P. Coaches */
    case 0x005038C8u: /* Options */
    case 0x0051BDD8u: /* Controller Assign (replaced by world on confirm) */
    case 0x0052C6FCu: /* Controller Setup */
    case 0x005408A8u: /* Extras */
    case 0x00508610u: /* Save VIP Record */
    case 0x00525FCCu: /* Xbox Live Sign-in */
    case 0x00529344u: /* Practice settings */
    case 0x00509844u: /* Basic Training Paused */
    case 0x004E9078u: /* Paused */
    case 0x004E8D70u: /* Pause quit/rematch */
        return 0;
    default:
        return 1;
    }
}
#endif
