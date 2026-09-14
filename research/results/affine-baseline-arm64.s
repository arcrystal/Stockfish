	.build_version macos, 27, 0	sdk_version 27, 0
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_final_affine                   ; -- Begin function final_affine
	.p2align	2
_final_affine:                          ; @final_affine
	.cfi_startproc
; %bb.0:
	movi.2d	v0, #0000000000000000
	ldp	q1, q2, [x1]
	ldp	q3, q4, [x0, #64]
	sdot.4s	v0, v1, v3
	sdot.4s	v0, v2, v4
	ldp	q1, q2, [x1, #32]
	ldp	q3, q4, [x0, #96]
	sdot.4s	v0, v1, v3
	sdot.4s	v0, v2, v4
	ldp	q1, q2, [x1, #64]
	ldp	q3, q4, [x0, #128]
	sdot.4s	v0, v1, v3
	sdot.4s	v0, v2, v4
	ldp	q1, q2, [x1, #96]
	ldp	q3, q4, [x0, #160]
	sdot.4s	v0, v1, v3
	sdot.4s	v0, v2, v4
	ldr	w8, [x0]
	addv.4s	s0, v0
	fmov	w9, s0
	add	w8, w8, w9
	str	w8, [x2]
	ret
	.cfi_endproc
                                        ; -- End function
.subsections_via_symbols
