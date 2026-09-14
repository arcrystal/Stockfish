	.build_version macos, 27, 0	sdk_version 27, 0
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_final_affine                   ; -- Begin function final_affine
	.p2align	2
_final_affine:                          ; @final_affine
	.cfi_startproc
; %bb.0:
	movi.2d	v0, #0000000000000000
	ldp	q2, q1, [x1]
	ldp	q4, q3, [x0, #64]
	sdot.4s	v0, v1, v3
	ldp	q3, q1, [x1, #32]
	ldp	q6, q5, [x0, #96]
	sdot.4s	v0, v1, v5
	ldp	q5, q1, [x1, #64]
	ldp	q16, q7, [x0, #128]
	sdot.4s	v0, v1, v7
	ldp	q7, q1, [x1, #96]
	ldp	q18, q17, [x0, #160]
	sdot.4s	v0, v1, v17
	movi.2d	v1, #0000000000000000
	sdot.4s	v1, v2, v4
	sdot.4s	v1, v3, v6
	sdot.4s	v1, v5, v16
	sdot.4s	v1, v7, v18
	add.4s	v0, v1, v0
	ldr	w8, [x0]
	addv.4s	s0, v0
	fmov	w9, s0
	add	w8, w9, w8
	str	w8, [x2]
	ret
	.cfi_endproc
                                        ; -- End function
.subsections_via_symbols
