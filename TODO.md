
- [x] Nice info for expressions (as nice as we can get now)
- [x] Option to enable (disabled by default) smart-segmentation,
- [x] Option to disable (enabled by default) expression deinflection.
- [x] Build scripts (makefiles).
- [x] Tests for everything (scripts and expression).
- [x] crfpp suck. Especially it's memory management. It would be nice to find other usable implementation.
  * Turns out it's most recent, performant (precision and recall) and easy to build implementation. So... rewrite 😞
  - [ ] FIND. MORE. DATA.
- [x] Second content script refactoring.
- [ ] Scoring for deinflections: -てよ is unlikely to be -ている->-てる->-てよ. よれよれ is unlikely to be 寄る(passive > masu stem) + よる(masu stem).
- [ ] Generate kanji.dat. KANJIDIC is good enough, but Wiktionary (en and jp) has entries it hasn't.
- [ ] Documentation
- [ ] Fix double UTF conversion (to UTF-8 when calling cpp code and back to UTF-16 in cpp code)
- [ ] Check if TreeWalker is really necessary or simple iteration through DOM would be fast enough.
- [ ] Japanese dictionary (lexicon). Sanseido is fine if it has offline version, but I prefer Wiktionary.
- [ ] Russian dictionary? And l10n then, I guess?
- [ ] Compile to WebAssembly and use it, when support detected.
- [ ] Extract and process text from pictures!
