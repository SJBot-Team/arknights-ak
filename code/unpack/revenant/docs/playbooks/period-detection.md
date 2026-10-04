# Confirm or refute a repeating-XOR key by residue-class statistics

Verified on: Merge Cooking, Mystery Town (CDPH key-length confirmation and
false-hypothesis rejection).

To test whether a byte stream is repeating-XOR encrypted with period `p`, split
it into `p` residue classes (byte `i` goes to class `i mod p`) and look at each
class's byte histogram. Under a genuine repeating key, each class is a single
byte XORed against structured plaintext, so its histogram has a dominant mode.
Under the wrong hypothesis, every class looks uniform.

Two uses, both load-bearing:

- **Confirm** a key length recovered by
  [plaintext-pairing](plaintext-pairing.md): the period you measured should show
  a clear modal peak per class.
- **Refute** the "it's just repeating XOR" hypothesis before wasting time on it:
  if the modal fraction stays near random for every candidate period, the
  transform is not a repeating XOR, and you should reach for
  [emulate-dont-reimplement](emulate-dont-reimplement.md).

## Reading the numbers

For each candidate `p`, report the mean modal fraction across classes. A real
key length stands out; near-uniform everywhere means the assumption is wrong,
not that you have not found the length yet.
