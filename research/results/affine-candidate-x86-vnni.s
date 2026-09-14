	.build_version macos, 27, 0	sdk_version 27, 0
	.section	__TEXT,__text,regular,pure_instructions
	.globl	_final_affine                   ## -- Begin function final_affine
	.p2align	4
_final_affine:                          ## @final_affine
	.cfi_startproc
## %bb.0:
	pushq	%rbp
	.cfi_def_cfa_offset 16
	.cfi_offset %rbp, -16
	movq	%rsp, %rbp
	.cfi_def_cfa_register %rbp
	vpxor	%xmm0, %xmm0, %xmm0
	vmovdqa	(%rsi), %ymm1
	vmovdqa	32(%rsi), %ymm2
	vmovdqa	64(%rsi), %ymm3
	vmovdqa	96(%rsi), %ymm4
	vpxor	%xmm5, %xmm5, %xmm5
	{vex}	vpdpbusd	96(%rdi), %ymm2, %ymm5
	{vex}	vpdpbusd	160(%rdi), %ymm4, %ymm5
	{vex}	vpdpbusd	64(%rdi), %ymm1, %ymm0
	{vex}	vpdpbusd	128(%rdi), %ymm3, %ymm0
	vpaddd	%ymm5, %ymm0, %ymm0
	vextracti128	$1, %ymm0, %xmm1
	vpaddd	%xmm1, %xmm0, %xmm0
	vpshufd	$78, %xmm0, %xmm1               ## xmm1 = xmm0[2,3,0,1]
	vpaddd	%xmm0, %xmm1, %xmm0
	vpshufd	$85, %xmm0, %xmm1               ## xmm1 = xmm0[1,1,1,1]
	vpaddd	%xmm0, %xmm1, %xmm0
	vmovd	%xmm0, %eax
	addl	(%rdi), %eax
	movl	%eax, (%rdx)
	popq	%rbp
	vzeroupper
	retq
	.cfi_endproc
                                        ## -- End function
.subsections_via_symbols
