#ifndef NFL2K5_TEST_VP_CACHE_COLLISION_H
#define NFL2K5_TEST_VP_CACHE_COLLISION_H
/* Three MOVs write position, diffuse and texture output. Both programs hash
 * to A3202AA7 at slot zero, but read different inputs and produce different outputs. */
static const uint32_t vp_cache_collision[2][3][4] = {
    {{0,2102584,134217728,63488},{0,2099314,134217728,63512},{0,2101833,134217728,63561}},
    {{0,2101722,134217728,63488},{0,2101451,134217728,63512},{0,2097714,134217728,63561}},
};
#endif
