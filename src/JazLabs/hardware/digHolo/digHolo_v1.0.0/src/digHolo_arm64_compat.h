#pragma once

#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>

#define _CMP_EQ_OS 0
#define _CMP_LT_OS 1
#define _CMP_LE_OS 2
#define _CMP_LE_OQ _CMP_LE_OS
#define _CMP_GE_OS 5
#define _CMP_GT_OS 6
#define _MM_FROUND_TO_NEAREST_INT 0
#define _MM_FROUND_NO_EXC 0
#define _MM_ROUND_NEAREST 0

struct alignas(32) __m256 { float f[8]; };
struct alignas(32) __m256d { double d[4]; };
struct alignas(32) __m256i { int64_t q[4]; };
struct alignas(16) __m128 { float f[4]; };
struct alignas(16) __m128i { int64_t q[2]; };

inline int32_t* i32(__m256i& v) { return reinterpret_cast<int32_t*>(v.q); }
inline const int32_t* i32(const __m256i& v) { return reinterpret_cast<const int32_t*>(v.q); }
inline int16_t* i16(__m256i& v) { return reinterpret_cast<int16_t*>(v.q); }
inline const int16_t* i16(const __m256i& v) { return reinterpret_cast<const int16_t*>(v.q); }
inline uint8_t* u8(__m256i& v) { return reinterpret_cast<uint8_t*>(v.q); }
inline const uint8_t* u8(const __m256i& v) { return reinterpret_cast<const uint8_t*>(v.q); }
inline int32_t* i32(__m128i& v) { return reinterpret_cast<int32_t*>(v.q); }
inline const int32_t* i32(const __m128i& v) { return reinterpret_cast<const int32_t*>(v.q); }
inline int16_t* i16(__m128i& v) { return reinterpret_cast<int16_t*>(v.q); }
inline const int16_t* i16(const __m128i& v) { return reinterpret_cast<const int16_t*>(v.q); }
inline uint8_t* u8(__m128i& v) { return reinterpret_cast<uint8_t*>(v.q); }
inline const uint8_t* u8(const __m128i& v) { return reinterpret_cast<const uint8_t*>(v.q); }

inline void* _mm_malloc(size_t size, size_t alignment)
{
    void* ptr = nullptr;
    return posix_memalign(&ptr, alignment, size) == 0 ? ptr : nullptr;
}

inline void _mm_free(void* ptr) { free(ptr); }

inline __m256 _mm256_setzero_ps() { return {}; }
inline __m256d _mm256_setzero_pd() { return {}; }
inline __m256 _mm256_set1_ps(float a) { __m256 r; for (float& x : r.f) x = a; return r; }
inline __m256d _mm256_set1_pd(double a) { __m256d r; for (double& x : r.d) x = a; return r; }
inline __m256i _mm256_set1_epi32(int a) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = a; return r; }
inline __m256i _mm256_set1_epi16(int a) { __m256i r; for (int k = 0; k < 16; ++k) i16(r)[k] = static_cast<int16_t>(a); return r; }
inline __m256i _mm256_set1_epi64x(int64_t a) { __m256i r; for (auto& x : r.q) x = a; return r; }
inline __m128i _mm_set1_epi32(int a) { __m128i r; for (int k = 0; k < 4; ++k) i32(r)[k] = a; return r; }
inline __m128i _mm_set1_epi16(int a) { __m128i r; for (int k = 0; k < 8; ++k) i16(r)[k] = static_cast<int16_t>(a); return r; }

inline __m256 _mm256_set_ps(float e7, float e6, float e5, float e4, float e3, float e2, float e1, float e0)
{
    return {{e0, e1, e2, e3, e4, e5, e6, e7}};
}

inline __m256d _mm256_set_pd(double e3, double e2, double e1, double e0)
{
    return {{e0, e1, e2, e3}};
}

inline __m256i _mm256_set_epi32(int e7, int e6, int e5, int e4, int e3, int e2, int e1, int e0)
{
    __m256i r;
    int vals[8] = {e0, e1, e2, e3, e4, e5, e6, e7};
    std::memcpy(i32(r), vals, sizeof(vals));
    return r;
}

inline __m256i _mm256_set_epi8(
    char e31, char e30, char e29, char e28, char e27, char e26, char e25, char e24,
    char e23, char e22, char e21, char e20, char e19, char e18, char e17, char e16,
    char e15, char e14, char e13, char e12, char e11, char e10, char e9, char e8,
    char e7, char e6, char e5, char e4, char e3, char e2, char e1, char e0)
{
    __m256i r;
    uint8_t vals[32] = {
        static_cast<uint8_t>(e0), static_cast<uint8_t>(e1), static_cast<uint8_t>(e2), static_cast<uint8_t>(e3),
        static_cast<uint8_t>(e4), static_cast<uint8_t>(e5), static_cast<uint8_t>(e6), static_cast<uint8_t>(e7),
        static_cast<uint8_t>(e8), static_cast<uint8_t>(e9), static_cast<uint8_t>(e10), static_cast<uint8_t>(e11),
        static_cast<uint8_t>(e12), static_cast<uint8_t>(e13), static_cast<uint8_t>(e14), static_cast<uint8_t>(e15),
        static_cast<uint8_t>(e16), static_cast<uint8_t>(e17), static_cast<uint8_t>(e18), static_cast<uint8_t>(e19),
        static_cast<uint8_t>(e20), static_cast<uint8_t>(e21), static_cast<uint8_t>(e22), static_cast<uint8_t>(e23),
        static_cast<uint8_t>(e24), static_cast<uint8_t>(e25), static_cast<uint8_t>(e26), static_cast<uint8_t>(e27),
        static_cast<uint8_t>(e28), static_cast<uint8_t>(e29), static_cast<uint8_t>(e30), static_cast<uint8_t>(e31),
    };
    std::memcpy(u8(r), vals, sizeof(vals));
    return r;
}

inline __m256 _mm256_loadu_ps(const float* p) { __m256 r; std::memcpy(r.f, p, sizeof(r.f)); return r; }
inline void _mm256_storeu_ps(float* p, __m256 a) { std::memcpy(p, a.f, sizeof(a.f)); }
inline __m128 _mm_loadu_ps(const float* p) { __m128 r; std::memcpy(r.f, p, sizeof(r.f)); return r; }
inline __m256i _mm256_loadu_si256(const __m256i* p) { __m256i r; std::memcpy(&r, p, sizeof(r)); return r; }
inline void _mm256_storeu_si256(__m256i* p, __m256i a) { std::memcpy(p, &a, sizeof(a)); }
inline __m128i _mm_loadu_si128(const __m128i* p) { __m128i r; std::memcpy(&r, p, sizeof(r)); return r; }
inline void _mm_storeu_si128(__m128i* p, __m128i a) { std::memcpy(p, &a, sizeof(a)); }

#define BIN_PS(name, op) inline __m256 name(__m256 a, __m256 b) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = a.f[k] op b.f[k]; return r; }
BIN_PS(_mm256_add_ps, +)
BIN_PS(_mm256_sub_ps, -)
BIN_PS(_mm256_mul_ps, *)
BIN_PS(_mm256_div_ps, /)
#undef BIN_PS

#define BIN_PD(name, op) inline __m256d name(__m256d a, __m256d b) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = a.d[k] op b.d[k]; return r; }
BIN_PD(_mm256_add_pd, +)
BIN_PD(_mm256_sub_pd, -)
BIN_PD(_mm256_mul_pd, *)
#undef BIN_PD

inline __m256 _mm256_fmadd_ps(__m256 a, __m256 b, __m256 c) { return _mm256_add_ps(_mm256_mul_ps(a, b), c); }
inline __m256d _mm256_fmadd_pd(__m256d a, __m256d b, __m256d c) { return _mm256_add_pd(_mm256_mul_pd(a, b), c); }
inline __m256 _mm256_fmaddsub_ps(__m256 a, __m256 b, __m256 c)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) r.f[k] = a.f[k] * b.f[k] + (k % 2 == 0 ? -c.f[k] : c.f[k]);
    return r;
}
inline __m256 _mm256_addsub_ps(__m256 a, __m256 b)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) r.f[k] = a.f[k] + (k % 2 == 0 ? -b.f[k] : b.f[k]);
    return r;
}

inline __m256 _mm256_min_ps(__m256 a, __m256 b) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::fmin(a.f[k], b.f[k]); return r; }
inline __m256 _mm256_max_ps(__m256 a, __m256 b) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::fmax(a.f[k], b.f[k]); return r; }
inline __m256d _mm256_min_pd(__m256d a, __m256d b) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = std::fmin(a.d[k], b.d[k]); return r; }
inline __m256d _mm256_max_pd(__m256d a, __m256d b) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = std::fmax(a.d[k], b.d[k]); return r; }
inline __m256 _mm256_sqrt_ps(__m256 a) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::sqrt(a.f[k]); return r; }
inline __m256 _mm256_rsqrt_ps(__m256 a) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = 1.0f / std::sqrt(a.f[k]); return r; }
inline __m256 _mm256_rcp_ps(__m256 a) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = 1.0f / a.f[k]; return r; }
inline __m256 _mm256_floor_ps(__m256 a) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::floor(a.f[k]); return r; }
inline __m256d _mm256_floor_pd(__m256d a) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = std::floor(a.d[k]); return r; }
inline __m256 _mm256_round_ps(__m256 a, int) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::nearbyint(a.f[k]); return r; }
inline __m256d _mm256_round_pd(__m256d a, int) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = std::nearbyint(a.d[k]); return r; }

inline __m256 _mm256_cmp_ps(__m256 a, __m256 b, int pred)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) {
        bool ok = pred == _CMP_EQ_OS ? a.f[k] == b.f[k] : pred == _CMP_LT_OS ? a.f[k] < b.f[k] : pred == _CMP_LE_OS ? a.f[k] <= b.f[k] : pred == _CMP_GE_OS ? a.f[k] >= b.f[k] : a.f[k] > b.f[k];
        uint32_t bits = ok ? 0xffffffffu : 0u;
        std::memcpy(&r.f[k], &bits, sizeof(bits));
    }
    return r;
}

inline __m256d _mm256_cmp_pd(__m256d a, __m256d b, int pred)
{
    __m256d r;
    for (int k = 0; k < 4; ++k) {
        bool ok = pred == _CMP_EQ_OS ? a.d[k] == b.d[k] : pred == _CMP_LT_OS ? a.d[k] < b.d[k] : pred == _CMP_LE_OS ? a.d[k] <= b.d[k] : pred == _CMP_GE_OS ? a.d[k] >= b.d[k] : a.d[k] > b.d[k];
        uint64_t bits = ok ? 0xffffffffffffffffull : 0ull;
        std::memcpy(&r.d[k], &bits, sizeof(bits));
    }
    return r;
}

inline __m256 bitwise_ps(__m256 a, __m256 b, char op)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) {
        uint32_t x, y, z;
        std::memcpy(&x, &a.f[k], 4);
        std::memcpy(&y, &b.f[k], 4);
        z = op == '&' ? (x & y) : op == '|' ? (x | y) : (x ^ y);
        std::memcpy(&r.f[k], &z, 4);
    }
    return r;
}
inline __m256 _mm256_and_ps(__m256 a, __m256 b) { return bitwise_ps(a, b, '&'); }
inline __m256 _mm256_or_ps(__m256 a, __m256 b) { return bitwise_ps(a, b, '|'); }
inline __m256 _mm256_xor_ps(__m256 a, __m256 b) { return bitwise_ps(a, b, '^'); }
inline __m256 _mm256_andnot_ps(__m256 a, __m256 b)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) {
        uint32_t x, y, z;
        std::memcpy(&x, &a.f[k], 4);
        std::memcpy(&y, &b.f[k], 4);
        z = ~x & y;
        std::memcpy(&r.f[k], &z, 4);
    }
    return r;
}

inline __m256d _mm256_and_pd(__m256d a, __m256d b)
{
    __m256d r;
    for (int k = 0; k < 4; ++k) {
        uint64_t x, y, z;
        std::memcpy(&x, &a.d[k], 8);
        std::memcpy(&y, &b.d[k], 8);
        z = x & y;
        std::memcpy(&r.d[k], &z, 8);
    }
    return r;
}

inline __m256 _mm256_blend_ps(__m256 a, __m256 b, int mask)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) r.f[k] = (mask & (1 << k)) ? b.f[k] : a.f[k];
    return r;
}
inline __m256 _mm256_blendv_ps(__m256 a, __m256 b, __m256 mask)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) {
        uint32_t m;
        std::memcpy(&m, &mask.f[k], 4);
        r.f[k] = (m & 0x80000000u) ? b.f[k] : a.f[k];
    }
    return r;
}

inline __m256 _mm256_shuffle_ps(__m256 a, __m256 b, int imm)
{
    __m256 r;
    for (int lane = 0; lane < 2; ++lane) {
        int base = lane * 4;
        r.f[base + 0] = a.f[base + ((imm >> 0) & 3)];
        r.f[base + 1] = a.f[base + ((imm >> 2) & 3)];
        r.f[base + 2] = b.f[base + ((imm >> 4) & 3)];
        r.f[base + 3] = b.f[base + ((imm >> 6) & 3)];
    }
    return r;
}
inline __m256 _mm256_permute_ps(__m256 a, int imm) { return _mm256_shuffle_ps(a, a, imm); }
inline __m256d _mm256_permute_pd(__m256d a, int imm)
{
    __m256d r;
    for (int lane = 0; lane < 2; ++lane) {
        r.d[lane * 2] = a.d[lane * 2 + ((imm >> (lane * 2)) & 1)];
        r.d[lane * 2 + 1] = a.d[lane * 2 + ((imm >> (lane * 2 + 1)) & 1)];
    }
    return r;
}
inline __m256 _mm256_permutevar8x32_ps(__m256 a, __m256i idx)
{
    __m256 r;
    for (int k = 0; k < 8; ++k) r.f[k] = a.f[i32(idx)[k] & 7];
    return r;
}
inline __m256i _mm256_permutevar8x32_epi32(__m256i a, __m256i idx)
{
    __m256i r;
    for (int k = 0; k < 8; ++k) i32(r)[k] = i32(a)[i32(idx)[k] & 7];
    return r;
}
inline __m256 _mm256_permute2f128_ps(__m256 a, __m256 b, int imm)
{
    __m256 r;
    const __m256* src[2] = {&a, &b};
    int sel0 = imm & 3;
    int sel1 = (imm >> 4) & 3;
    for (int k = 0; k < 4; ++k) r.f[k] = src[sel0 >> 1]->f[(sel0 & 1) * 4 + k];
    for (int k = 0; k < 4; ++k) r.f[4 + k] = src[sel1 >> 1]->f[(sel1 & 1) * 4 + k];
    return r;
}
inline __m256d _mm256_permute2f128_pd(__m256d a, __m256d b, int imm)
{
    __m256d r;
    const __m256d* src[2] = {&a, &b};
    int sel0 = imm & 3;
    int sel1 = (imm >> 4) & 3;
    for (int k = 0; k < 2; ++k) r.d[k] = src[sel0 >> 1]->d[(sel0 & 1) * 2 + k];
    for (int k = 0; k < 2; ++k) r.d[2 + k] = src[sel1 >> 1]->d[(sel1 & 1) * 2 + k];
    return r;
}
inline __m256i _mm256_permute2f128_si256(__m256i a, __m256i b, int imm)
{
    __m256i r;
    const int64_t* src[2] = {a.q, b.q};
    int sel0 = imm & 3;
    int sel1 = (imm >> 4) & 3;
    for (int k = 0; k < 2; ++k) r.q[k] = src[sel0 >> 1][(sel0 & 1) * 2 + k];
    for (int k = 0; k < 2; ++k) r.q[2 + k] = src[sel1 >> 1][(sel1 & 1) * 2 + k];
    return r;
}
inline __m256i _mm256_permute4x64_epi64(__m256i a, int imm)
{
    __m256i r;
    for (int k = 0; k < 4; ++k) r.q[k] = a.q[(imm >> (2 * k)) & 3];
    return r;
}

#define BIN_I32(name, op) inline __m256i name(__m256i a, __m256i b) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = i32(a)[k] op i32(b)[k]; return r; }
BIN_I32(_mm256_add_epi32, +)
BIN_I32(_mm256_sub_epi32, -)
BIN_I32(_mm256_mullo_epi32, *)
BIN_I32(_mm256_and_si256, &)
BIN_I32(_mm256_or_si256, |)
#undef BIN_I32
inline __m256i _mm256_andnot_si256(__m256i a, __m256i b) { __m256i r; for (int k = 0; k < 4; ++k) r.q[k] = ~a.q[k] & b.q[k]; return r; }
inline __m128i _mm_add_epi32(__m128i a, __m128i b) { __m128i r; for (int k = 0; k < 4; ++k) i32(r)[k] = i32(a)[k] + i32(b)[k]; return r; }
inline __m128i _mm_sub_epi32(__m128i a, __m128i b) { __m128i r; for (int k = 0; k < 4; ++k) i32(r)[k] = i32(a)[k] - i32(b)[k]; return r; }
inline __m128i _mm_slli_epi32(__m128i a, int s) { __m128i r; for (int k = 0; k < 4; ++k) i32(r)[k] = i32(a)[k] << s; return r; }
inline __m256i _mm256_slli_epi32(__m256i a, int s) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = i32(a)[k] << s; return r; }
inline __m256i _mm256_srli_epi32(__m256i a, int s) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = static_cast<uint32_t>(i32(a)[k]) >> s; return r; }
inline __m256i _mm256_slli_epi64(__m256i a, int s) { __m256i r; for (int k = 0; k < 4; ++k) r.q[k] = a.q[k] << s; return r; }
inline __m256i _mm256_srli_epi64(__m256i a, int s) { __m256i r; for (int k = 0; k < 4; ++k) r.q[k] = static_cast<uint64_t>(a.q[k]) >> s; return r; }
inline __m256i _mm256_cmpeq_epi32(__m256i a, __m256i b) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = i32(a)[k] == i32(b)[k] ? -1 : 0; return r; }
inline __m256i _mm256_cmpgt_epi32(__m256i a, __m256i b) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = i32(a)[k] > i32(b)[k] ? -1 : 0; return r; }
inline __m256i _mm256_max_epi32(__m256i a, __m256i b) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = i32(a)[k] > i32(b)[k] ? i32(a)[k] : i32(b)[k]; return r; }
inline int _mm256_testz_si256(__m256i a, __m256i b) { for (int k = 0; k < 4; ++k) if ((a.q[k] & b.q[k]) != 0) return 0; return 1; }

inline __m256i _mm256_cvtps_epi32(__m256 a) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = static_cast<int32_t>(std::lrint(a.f[k])); return r; }
inline __m256i _mm256_cvttps_epi32(__m256 a) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = static_cast<int32_t>(a.f[k]); return r; }
inline __m256 _mm256_cvtepi32_ps(__m256i a) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = static_cast<float>(i32(a)[k]); return r; }
inline __m256d _mm256_cvtepi32_pd(__m128i a) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = static_cast<double>(i32(a)[k]); return r; }
inline __m128i _mm256_cvtpd_epi32(__m256d a) { __m128i r = {}; for (int k = 0; k < 4; ++k) i32(r)[k] = static_cast<int32_t>(std::lrint(a.d[k])); return r; }
inline __m128 _mm256_cvtpd_ps(__m256d a) { __m128 r; for (int k = 0; k < 4; ++k) r.f[k] = static_cast<float>(a.d[k]); return r; }
inline __m256d _mm256_cvtps_pd(__m128 a) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = a.f[k]; return r; }
inline __m256i _mm256_cvtepi16_epi32(__m128i a) { __m256i r; for (int k = 0; k < 8; ++k) i32(r)[k] = i16(a)[k]; return r; }
inline __m256i _mm256_cvtepu16_epi32(__m128i a) { __m256i r; auto p = reinterpret_cast<const uint16_t*>(a.q); for (int k = 0; k < 8; ++k) i32(r)[k] = p[k]; return r; }
inline __m256i _mm256_cvtepi32_epi64(__m128i a) { __m256i r; for (int k = 0; k < 4; ++k) r.q[k] = i32(a)[k]; return r; }
inline __m128i _mm256_cvtepi64_epi32(__m256i a) { __m128i r; for (int k = 0; k < 4; ++k) i32(r)[k] = static_cast<int32_t>(a.q[k]); return r; }

inline __m256 _mm256_castsi256_ps(__m256i a) { __m256 r; std::memcpy(&r, &a, sizeof(r)); return r; }
inline __m256i _mm256_castps_si256(__m256 a) { __m256i r; std::memcpy(&r, &a, sizeof(r)); return r; }
inline __m256d _mm256_castsi256_pd(__m256i a) { __m256d r; std::memcpy(&r, &a, sizeof(r)); return r; }
inline __m256i _mm256_castpd_si256(__m256d a) { __m256i r; std::memcpy(&r, &a, sizeof(r)); return r; }
inline __m128 _mm_castsi128_ps(__m128i a) { __m128 r; std::memcpy(&r, &a, sizeof(r)); return r; }
inline __m128 _mm256_castps256_ps128(__m256 a) { __m128 r; std::memcpy(&r, a.f, sizeof(r)); return r; }
inline __m256 _mm256_castps128_ps256(__m128 a) { __m256 r = {}; std::memcpy(r.f, &a, sizeof(a)); return r; }

inline __m128i _mm256_extractf128_si256(__m256i a, int imm) { __m128i r; std::memcpy(&r, &a.q[(imm & 1) * 2], sizeof(r)); return r; }
inline __m128i _mm256_extracti128_si256(__m256i a, int imm) { return _mm256_extractf128_si256(a, imm); }
inline __m256 _mm256_insertf128_ps(__m256 a, __m128 b, int imm) { std::memcpy(&a.f[(imm & 1) * 4], b.f, sizeof(b.f)); return a; }
inline __m256i _mm256_insertf128_si256(__m256i a, __m128i b, int imm) { std::memcpy(&a.q[(imm & 1) * 2], &b, sizeof(b)); return a; }

inline __m256i _mm256_packs_epi32(__m256i a, __m256i b)
{
    __m256i r;
    for (int k = 0; k < 8; ++k) i16(r)[k] = static_cast<int16_t>(i32(a)[k]);
    for (int k = 0; k < 8; ++k) i16(r)[8 + k] = static_cast<int16_t>(i32(b)[k]);
    return r;
}
inline __m256i _mm256_packus_epi32(__m256i a, __m256i b) { return _mm256_packs_epi32(a, b); }
inline __m256i _mm256_packus_epi16(__m256i a, __m256i b)
{
    __m256i r;
    for (int k = 0; k < 16; ++k) u8(r)[k] = static_cast<uint8_t>(i16(a)[k]);
    for (int k = 0; k < 16; ++k) u8(r)[16 + k] = static_cast<uint8_t>(i16(b)[k]);
    return r;
}
inline __m256i _mm256_madd_epi16(__m256i a, __m256i b)
{
    __m256i r;
    for (int k = 0; k < 8; ++k) i32(r)[k] = i16(a)[2 * k] * i16(b)[2 * k] + i16(a)[2 * k + 1] * i16(b)[2 * k + 1];
    return r;
}
inline __m256i _mm256_shuffle_epi8(__m256i a, __m256i mask)
{
    __m256i r = {};
    for (int lane = 0; lane < 2; ++lane) {
        for (int k = 0; k < 16; ++k) {
            uint8_t m = u8(mask)[lane * 16 + k];
            u8(r)[lane * 16 + k] = (m & 0x80) ? 0 : u8(a)[lane * 16 + (m & 0x0f)];
        }
    }
    return r;
}
inline __m256i _mm256_i32gather_epi32(const int* base, __m256i idx, int scale)
{
    __m256i r;
    for (int k = 0; k < 8; ++k) i32(r)[k] = *reinterpret_cast<const int*>(reinterpret_cast<const char*>(base) + i32(idx)[k] * scale);
    return r;
}

inline __m256 _mm256_hadd_ps(__m256 a, __m256 b)
{
    return {{a.f[0] + a.f[1], a.f[2] + a.f[3], b.f[0] + b.f[1], b.f[2] + b.f[3],
             a.f[4] + a.f[5], a.f[6] + a.f[7], b.f[4] + b.f[5], b.f[6] + b.f[7]}};
}

inline __m256 _mm256_exp_ps(__m256 a) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::exp(a.f[k]); return r; }
inline __m256d _mm256_exp_pd(__m256d a) { __m256d r; for (int k = 0; k < 4; ++k) r.d[k] = std::exp(a.d[k]); return r; }
inline __m256 _mm256_sin_ps(__m256 a) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::sin(a.f[k]); return r; }
inline __m256 _mm256_sincos_ps(__m256* c, __m256 a) { __m256 s; for (int k = 0; k < 8; ++k) { s.f[k] = std::sin(a.f[k]); c->f[k] = std::cos(a.f[k]); } return s; }
inline __m256 _mm256_atan2_ps(__m256 y, __m256 x) { __m256 r; for (int k = 0; k < 8; ++k) r.f[k] = std::atan2(y.f[k], x.f[k]); return r; }
