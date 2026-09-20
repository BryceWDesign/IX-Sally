# CUC-2: Generative Open Choice

CUC-2 addresses a specific limitation of CUC-1: CUC-1 can choose among an evaluator-supplied finite action menu, but cannot author a complete action outside that menu.

CUC-2 separates primitive capabilities from complete actions. Sally may compose primitives into a new action program that was not enumerated by the environment. The grammar can generate arbitrarily many finite compositions; each deliberation is explicitly bounded by depth and exploration budgets.

The reference experiment begins at integer state `3` with target `11`. The offered menu contains four single-step actions: increment, decrement, double, and negate. None reaches `11`. Sally's open-choice synthesizer constructs a multi-step program from the primitives that reaches the target, demonstrating a successful alternative outside the offered menu.

The same subsystem includes:

- **Deliberation reopening:** surprise, context shift, conflict, a valuable novel alternative, or insufficient confidence can reopen deliberation instead of blindly executing a promoted habit.
- **Minimal sufficiency:** Sally can remove operations from a successful program and retain the reduced program only when an independent goal test still passes. This implements a safe form of assumption/constraint questioning rather than treating every supplied step as mandatory.
- **Bounded execution:** generative choice does not mean infinite runtime. Search depth and explored-program budgets remain explicit.

## Claim boundary

CUC-2 demonstrates bounded generative action construction. It is not evidence of AGI, consciousness, free will, or literally infinite computation. It does establish a stronger property than finite menu selection: the complete selected action need not exist before deliberation begins.
