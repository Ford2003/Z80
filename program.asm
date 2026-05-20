        org $0000
        fill $00

 ; Memory Map:
 ; 0000h - 1FFFh : ROM
 ; 2000h - 3FFFh : RAM



 ; Put ffffh into BC
 ; On each iteration do Decrement BC and jump if Z is not set
start:
        LD BC, 0ffffh

loop:
        DEC BC          ; Decrement BC, no conditional registers affected
        LD A, B         ; Load high byte B into A. No condition bits affected
        OR C            ; Logical OR with low byte. Sets Z if result is 0.
        JR NZ, loop     ; If Z is 1 continue (BC is zero) else jump to loop




        org $1FFD
return_to_start:
        JP 0000h