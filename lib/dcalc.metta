;; MeTTaDinC M0: MeTTa-side entry points for the native CeTTa module "dcalc"
;; (upstream/cetta patches: src/library_dcalc.{h,c}).  The core is the C code
;; in src/dcalc; this file adds no semantics of its own.
;;
;;   !(import! &self dcalc)                 ; the native module (import bit 23, provisional)
;;   !(import! &self lib/dcalc)             ; this file
;;   !(dc.run-file "fixtures/eight_state.metta" EightState AB)
;;   !(dc.run-source "(DC.Module M ...)" M (MeasureNow R))
;;
;; Every call returns one result envelope
;;   (Result (Status S) (Claim ..) (Binding ..) (Scope ..) (Value ..)
;;           (Evidence ..) (Assumptions ..) (Assurance ..) [(Reason ..)])
;; where S is one of Checked Refuted Conditional Estimated Unknown
;; Unsupported InvalidInput, assigned by the core's single assurance policy.
;; The request argument is data: CeTTa hands it to the core unevaluated
;; (grounded_dispatch_accepts_data_arg exception for dcalc:run / dcalc:run-file).
;; No (: dc.* ...) type declarations on purpose: with Atom-typed results CeTTa
;; returns the dcalc:* call unreduced (review 2 finding 1).  Tested by
;; tests/dcalc/cetta/surface.metta.

(= (dc.run-file $path $module $request) (dcalc:run-file $path $module $request))

(= (dc.run-source $source $module $request) (dcalc:run $source $module $request))

;; Field access on an envelope, by head symbol.
(= (dc.field $env $name)
   (case $env
     (((Result (Status $s) $c $b $sc $v $e $a $as) (dc.pick $name $s $c $b $sc $v $e $a $as Empty))
      ((Result (Status $s) $c $b $sc $v $e $a $as $r) (dc.pick $name $s $c $b $sc $v $e $a $as $r))
      ((Result (Status $s) $b $r) (dc.pick $name $s Empty $b Empty Empty Empty Empty Empty $r)))))

(= (dc.pick Status $s $c $b $sc $v $e $a $as $r) $s)
(= (dc.pick Claim $s $c $b $sc $v $e $a $as $r) $c)
(= (dc.pick Binding $s $c $b $sc $v $e $a $as $r) $b)
(= (dc.pick Scope $s $c $b $sc $v $e $a $as $r) $sc)
(= (dc.pick Value $s $c $b $sc $v $e $a $as $r) $v)
(= (dc.pick Evidence $s $c $b $sc $v $e $a $as $r) $e)
(= (dc.pick Assumptions $s $c $b $sc $v $e $a $as $r) $a)
(= (dc.pick Assurance $s $c $b $sc $v $e $a $as $r) $as)
(= (dc.pick Reason $s $c $b $sc $v $e $a $as $r) $r)

(= (dc.status $env) (dc.field $env Status))
