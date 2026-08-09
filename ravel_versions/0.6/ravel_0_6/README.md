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

The current extraction compiles these pieces through a deterministic unity
wrapper. This preserves the generated candidate's static linkage and behavior
while making every component byte-addressable in the build manifest. It is a
physical source decomposition, not a claim that independently compiled C ABI
contracts or evaluator authority already exist. Promoting a component to a
separately compiled unit requires a separately reviewed header contract and a
new parity fixture.
