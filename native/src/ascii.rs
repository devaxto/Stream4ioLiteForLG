//! Scalar ARMv7 routine: no NEON, no out-of-range read, no allocator or OS calls.
//! This is opt-in. Correctness is testable; speed requires measurements on the TV.
#[cfg(all(target_arch = "arm", feature = "arm-asm"))]
core::arch::global_asm!(include_str!("ascii_arm.S"));

#[cfg(all(target_arch = "arm", feature = "arm-asm"))]
extern "C" {
    fn streamlite_ascii_lower(ptr: *mut u8, len: usize);
}

pub fn lower(bytes: &mut [u8]) {
    #[cfg(all(target_arch = "arm", feature = "arm-asm"))]
    // SAFETY: the routine writes exactly len bytes in the exclusive slice and
    // preserves r4-r11, sp and lr per AAPCS. It never follows untrusted pointers.
    unsafe {
        streamlite_ascii_lower(bytes.as_mut_ptr(), bytes.len());
    }
    #[cfg(not(all(target_arch = "arm", feature = "arm-asm")))]
    bytes.make_ascii_lowercase();
}

pub fn self_test() -> bool {
    for len in 0..=256 {
        // Include sentinels and every byte, including UTF-8 continuation bytes.
        let mut actual: Vec<u8> = (0..=255).collect();
        let mut expected = actual.clone();
        expected[..len].make_ascii_lowercase();
        lower(&mut actual[..len]);
        if actual != expected {
            return false;
        }
    }
    true
}
