
- [x] Nice info for expressions (as nice as we can get now)
- [x] Option to enable (disabled by default) smart-segmentation,
option to disable (enabled by default) expression deinflection.
- [ ] Tests for everything (scripts and expression).
- [ ] Build scripts.
- [ ] crfpp suck. Especially it's memory management. It would be nice to find other usable implementation.
  * Turns out it's most recent, performant (precision and recall) and easy to build implementation. So... rewrite 😞
- [ ] Documentation + second content script refactoring.
- [ ] Check if TreeWalker is really necessary or simple iteration through DOM would be fast enough.
- [ ] Generate kanji.dat. KANJIDIC is good enough, but Wiktionary (en and jp) has entries it hasn't.
- [ ] Japanese dictionary (lexicon). Sanseido is fine if it has offline version, but I prefer Wiktionary.
- [ ] Russian dictionary? And l10n then, I guess?
- [ ] Compile to WebAssembly and use it, when support detected.
- [ ] Extract and process text from pictures!
