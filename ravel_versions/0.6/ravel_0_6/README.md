# RAVEL 0.6 generated component boundary

The 0.6 development build derives candidate-001 from the frozen 0.5 source,
then losslessly splits the generated text into bounded include units:

- preamble and shared types;
- core mechanism state and learning;
- world/provider generation;
- transition compilation;
- planning;
- checkpoint codec;
- observations and adaptation transaction;
- reporting;
- trial driver.

The current extraction retains a deterministic unity wrapper as a parity
oracle. The checkpoint byte-comparison operation is now promoted to the first
separately compiled unit under `ravel-0.6-checkpoint-abi/1`; the candidate
object links against `ravel_0_6_checkpoint.o` while the unity binary remains
available. The remaining mechanism surfaces are still include units and are
not claimed to have independent C ABI contracts. This is local development
execution, not independent evaluation or authority.
