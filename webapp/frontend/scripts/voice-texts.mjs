// Prints every line Titan can say from pre-recorded audio, as JSON. Used by
// scripts/build_titan_voice.py at the repo root.
import { GUIDE } from '../src/guideKnowledge.js'
import { allReplyTexts, HELLO } from '../src/titanCommands.js'

const texts = [HELLO, ...GUIDE.map((g) => g.a), ...allReplyTexts()]
process.stdout.write(JSON.stringify([...new Set(texts)]))
