import unittest
import sys
import random
import secrets
import bisect
import itertools
from ctypes import (
	cdll,
	c_char,
	c_char_p,
	c_void_p,
	c_ushort,
	c_uint,
	cast,
	CFUNCTYPE,
	POINTER,
	pointer,
	Structure,
	c_size_t,
	c_bool,
	c_int,
	sizeof,
	byref,
	c_ubyte,
	create_string_buffer,
	string_at
)

sys.path.append('../data')
from utils import kata_to_hira

lib = cdll.LoadLibrary('build/test.so')

InputData = c_ushort * 32
InputLengthMapping = c_ubyte * 32
class Input(Structure):
	_fields_ = [
		('data', InputData),
		('length_mapping', InputLengthMapping),
		('length', c_ubyte),
	]
pInput = POINTER(Input)

class Buffer(Structure):
	_fields_ = [
		('capacity', c_size_t),
		('size', c_size_t),
		('data', c_void_p),
	]
pBuffer = POINTER(Buffer)

def make_buffer(capacity):
	memory = create_string_buffer(capacity)
	buf = Buffer(capacity, 0, cast(pointer(memory), c_void_p))
	return memory, buf

class State(Structure):
	_fields_ = [
		('input', Input),
		('buffers', Buffer * 6),
	]
pState = POINTER(State)

class Candidate(Structure):
	_fields_ = [
		('word_length', c_size_t),
		('word', POINTER(c_ushort)),
		('inflection_name_length', c_size_t),
		('inflection_name', c_char_p),
		('type', c_uint),
	]

	def get_word(self):
		return ''.join(map(chr, self.word[:self.word_length]))

	def get_inflection_name(self):
		return self.inflection_name[:self.inflection_name_length].decode()

	def __repr__(self):
		return ', '.join([
			f'Candidate({self.word_length}',
			self.get_word(),
			f'{self.inflection_name_length}',
			self.get_inflection_name(),
			f'0x{self.type:08X})'
		])

class DictionaryIndex(Structure):
	_fields_ = [
		('last_chunk_index', c_size_t),
		('last_chunk_size', c_size_t),
		('original_size', c_size_t),
		('chunks_offsets', POINTER(c_uint)),
		('data', POINTER(c_ubyte)),
		('currently_decompressed_chunk_index', c_size_t),
	]
pDictionaryIndex = POINTER(DictionaryIndex)
test_index = DictionaryIndex(
	c_size_t.in_dll(lib, 'test_dictionary_index_last_chunk_index'),
	c_size_t.in_dll(lib, 'test_dictionary_index_last_chunk_size'),
	c_size_t.in_dll(lib, 'test_dictionary_index_original_size'),
	cast(lib.test_dictionary_index_chunks_offsets, POINTER(c_uint)),
	cast(lib.test_dictionary_index_data, POINTER(c_ubyte)),
	c_size_t(-1)
)

class DictionaryIndexEntry(Structure):
	_fields_ = [
		('start_position_in_index', c_size_t),
		('end_position_in_index', c_size_t),
		('key_length', c_size_t),
		('num_offsets', c_size_t),
		('vardata_start_offset', c_size_t),
	]
pDictionaryIndexEntry = POINTER(DictionaryIndexEntry)

class Iterator(Structure):
	_fields_ = [
		('current', c_void_p),
		('end', c_void_p),
	]
pIterator = POINTER(Iterator)

class CurrentIndexEntry(Structure):
	_fields_ = [
		('start_position_in_index', c_size_t),
		('end_position_in_index', c_size_t),
		('key_length', c_size_t),
		('key', POINTER(c_ushort)),
		('num_offsets', c_size_t),
		('offsets', POINTER(c_uint)),
	]

class Surface(Structure):
	_fields_ = [
		('text', c_char_p),
		('length', c_size_t),
		('common', c_bool),
	]
Kanji = Surface
pKanji = POINTER(Kanji)
Reading = Surface
pReading = POINTER(Reading)

class KanjiGroup(Structure):
	_fields_ = [
		('num_reading_indices', c_size_t),
		('reading_indices', POINTER(c_ubyte)),

		('num_kanjis', c_size_t),
		('kanjis', pKanji),
	]
pKanjiGroup = POINTER(KanjiGroup)

class BorrowedString(Structure):
	_fields_ = [
		('text', c_char_p),
		('length', c_size_t),
	]
pBorrowedString = POINTER(BorrowedString)

class SenseGroup(Structure):
	_fields_ = [
		('num_types', c_size_t),
		('types', pBorrowedString),

		('num_senses', c_size_t),
		('senses', pBorrowedString),
	]
pSenseGroup = POINTER(SenseGroup)

class Dentry(Structure):
	_fields_ = [
		('kanjis_start', c_char_p),
		('readings_start', c_char_p),
		('definition_start', c_char_p),
		('definition_end', c_char_p),
		('freq', c_int),

		('num_kanji_groups', c_size_t),
		('kanji_groups', pKanjiGroup),

		('num_readings', c_size_t),
		('readings', pReading),

		('num_sense_groups', c_size_t),
		('sense_groups', pSenseGroup),
	]
pDentry = POINTER(Dentry)

class WordResult(Structure):
	_fields_ = [
		('offset', c_size_t),

		('vardata_start_offset', c_size_t),
		('key_length', c_ubyte),
		('inflection_name_length', c_ubyte),

		('match_utf16_length', c_ubyte),
		('is_name', c_bool),

		('dentry', pDentry),
	]
pWordResult = POINTER(WordResult)

dictionary_line = 'お浸し,御浸し;御ひたし#0;御したし#1\tおひたし;おしたし\tn;boiled greens in bonito-flavoured soy sauce\\p\t33066'
def make_dentry() -> Dentry:
	s = dictionary_line.encode()
	ends = [len(p) for p in s.split(b'\t')][:3]
	for i in range(1, len(ends)):
		ends[i] += ends[i - 1] + 1
		assert s[ends[i]] == ord('\t')

	buf = create_string_buffer(s)
	kanjis_start = cast(buf, c_char_p)
	readings_start = cast(pointer(c_char.from_buffer(buf, ends[0])), c_char_p)
	assert cast(readings_start, c_void_p).value > cast(kanjis_start, c_void_p).value
	definition_start = cast(pointer(c_char.from_buffer(buf, ends[1])), c_char_p)
	definition_end = cast(pointer(c_char.from_buffer(buf, ends[2])), c_char_p)

	k1 = Kanji(b'123', 3, True)
	kg1 = KanjiGroup(0, None, 1, pointer(k1))
	ks2 = (Kanji * 2)(Kanji(b'45', 2, False), Kanji(b'6789', 4, True))
	ri = c_ubyte(1)
	kg2 = KanjiGroup(1, pointer(ri), 2, cast(pointer(ks2), pKanji))
	kgs = (KanjiGroup * 2)(kg1, kg2)

	rs = (Reading * 2)(Reading(b'abc', 3, True), Reading(b'de', 2, False))

	t1 = BorrowedString(b'p', 1)
	s1 = BorrowedString(b'se', 2)
	sg1 = SenseGroup(1, pointer(t1), 1, pointer(s1))

	t2 = BorrowedString(b'm', 1)
	s2 = BorrowedString(b'ftw', 3)
	sg2 = SenseGroup(1, pointer(t2), 1, pointer(s2))
	sgs = (SenseGroup * 2)(sg1, sg2)

	return Dentry(
		kanjis_start, readings_start, definition_start, definition_end,
		123,
		2, cast(pointer(kgs), pKanjiGroup),
		2, cast(pointer(rs), pReading),
		2, cast(pointer(sgs), pSenseGroup),
	)

@CFUNCTYPE(None, c_char_p)
def take_a_trip(s):
	print('took a trip:', s.decode())
	exit(1)
c_void_p.in_dll(lib, 'take_a_trip_impl').value = cast(take_a_trip, c_void_p).value

lib.vardata_array_elements_start.argtypes = [pBuffer]
lib.vardata_array_elements_start.restype = c_void_p

lib.vardata_array_num_elements.argtypes = [pBuffer]
lib.vardata_array_num_elements.restype = c_size_t

lib.dictionary_index_get_entry.argtypes = [pDictionaryIndex, c_char_p, c_size_t]
lib.dictionary_index_get_entry.restype = pDictionaryIndexEntry

lib.state_get_index_entry_buffer.restype = pBuffer
lib.state_get_word_result_buffer.restype = pBuffer
lib.state_get_html_buffer.restype = pBuffer

lib.state_get_word_result_iterator.restype = Iterator

lib.word_result_iterator_next.argtypes = [pIterator]
lib.word_result_iterator_next.restype = None

lib.state_try_add_word_result.argtypes = [
	c_uint, c_size_t,
	c_char_p, c_size_t,
	c_char_p, c_size_t,
	c_size_t
]
lib.state_try_add_word_result.restype = c_bool

class T(unittest.TestCase):

	@classmethod
	def setUpClass(cls):
		cls.samples = {}
		with open('generated/index-samples.csv') as f:
			for l in f:
				l = l.strip().split(',')
				cls.samples[l[0]] = list(map(lambda o: tuple(map(int, o.split(';'))) if ';' in o else int(o), l[1:]))

	@classmethod
	def get_offsets(cls, key):
		return set(map(lambda o: o[1] if type(o) == tuple else o, cls.samples[key]))

	def init_state(self):
		size = (1 << 16) * 2
		self.memory = create_string_buffer(size)
		lib.init.argtypes = [c_void_p, c_size_t]
		lib.init.restype = None
		lib.init(cast(pointer(self.memory), c_void_p), size)
		self.state = pState.in_dll(lib, 'state')

	def clear_state(self):
		c_void_p.in_dll(lib, 'state').value = 0

		if hasattr(self, 'state'):
			del self.state

		if hasattr(self, 'memory'):
			del self.memory

	def tearDown(self):
		self.clear_state()
		c_void_p.in_dll(lib, 'currently_decompressed_index').value = 0

	def make_word_result(self) -> pWordResult:
		assert hasattr(self, 'memory')

		lib.state_try_add_word_result(
			0x1, 17,
			'abc'.encode('utf-16le'), 3,
			b'fake', 4,
			100500
		)

		d = make_dentry()
		buf = lib.state_get_word_result_buffer()
		res = cast(lib.vardata_array_elements_start(buf), pWordResult)
		res.contents.dentry = pointer(d)

		return res

	def _test_kata_to_hira_character(self):
		lib.kata_to_hira_character.argtypes = [c_ushort, c_ushort]
		lib.kata_to_hira_character.restype = c_uint

		prevs = [
			(0, '\0'),
			*((c, chr(c)) for c in range(ord('ぁ'), ord('ゔ'))),
			*((c, chr(c)) for c in range(ord('ｳ'), ord('ﾎ'))),
		]
		for code in range(0x3000, 0x9faf):
			for prev_code, prev_char in prevs:
				res = lib.kata_to_hira_character(code, prev_code)
				gold = kata_to_hira(prev_char + chr(code), agressive=False)
				if res & (1 << 16) != 0:
					self.assertEqual(chr(res & 0xffff), gold)
				else:
					self.assertEqual(chr(res), gold[-1])

		surrogate_pair = '櫛'.encode('utf-16le')
		for prev_code, prev_char in prevs:
			self.assertEqual(surrogate_pair[0], lib.kata_to_hira_character(surrogate_pair[0], prev_code))
			self.assertEqual(surrogate_pair[0], lib.kata_to_hira_character(surrogate_pair[0], surrogate_pair[1]))

			self.assertEqual(surrogate_pair[1], lib.kata_to_hira_character(surrogate_pair[1], prev_code))
			self.assertEqual(surrogate_pair[1], lib.kata_to_hira_character(surrogate_pair[1], surrogate_pair[0]))

		self.assertEqual(ord('を'), lib.kata_to_hira_character(ord('ｦ'), 0))
		self.assertEqual((1 << 16) | ord('ゔ'), lib.kata_to_hira_character(ord('ﾞ'), ord('う')))
		self.assertEqual((1 << 16) | ord('ぷ'), lib.kata_to_hira_character(ord('ﾟ'), ord('ふ')))

	def test_input_kata_to_hira(self):
		struct = Input()
		w = 'ｽﾋﾟｰｶ'
		for i, c in enumerate(w):
			struct.data[i] = ord(c)
		struct.length = len(w)
		lib.input_kata_to_hira(byref(struct))
		self.assertEqual(struct.length, 4)
		self.assertEqual(''.join(map(chr, struct.data[:4])), 'すぴいか')
		self.assertEqual(struct.length_mapping[:5], [0, 1, 3, 4, 5])

		w = '開発センター'
		for i, c in enumerate(w):
			struct.data[i] = ord(c)
		struct.length = len(w)
		lib.input_kata_to_hira(byref(struct))
		self.assertEqual(struct.length, 6)
		self.assertEqual(''.join(map(chr, struct.data[:6])), '開発せんたあ')
		self.assertEqual(struct.length_mapping[:6], [0, 1, 2, 3, 4, 5])

	def _binary_locate(self, S, array, needle, compar):
		lib.binary_locate.argtypes = [
			c_void_p, c_void_p,
			c_size_t, c_size_t,
			c_void_p, POINTER(c_bool)
		]
		lib.binary_locate.restype = c_void_p

		array = (S * len(array))(*array)
		array_ptr = cast(POINTER(S)(array), c_void_p)
		found = c_bool(False)
		it = lib.binary_locate(
			c_char_p(needle.encode()), array_ptr,
			len(array), sizeof(S),
			compar, byref(found)
		)
		index = (it - array_ptr.value) // sizeof(S)
		return found, index

	def test_binary_locate(self):
		class S(Structure):
			_fields_ = [
				('key', c_char_p),
				('flag', c_bool),
			]

		@CFUNCTYPE(c_int, c_void_p, c_void_p)
		def compar(k, v):
			a = cast(k, c_char_p).value
			b = cast(v, POINTER(S)).contents.key
			if a < b:
				return -1
			elif a > b:
				return 1
			else:
				return 0

		for i in range(24):
			keys = [secrets.token_urlsafe(random.randrange(3, 18)) for _ in range(i)]
			keys.sort()
			needle = secrets.token_urlsafe(random.randrange(1, 20))

			found, index = self._binary_locate(
				S, [S(k.encode(), random.choice([True, False])) for k in keys],
				needle, compar
			)
			self.assertFalse(found)
			self.assertEqual(index, bisect.bisect_left(keys, needle))

			bisect.insort_left(keys, needle)

			found, index = self._binary_locate(
				S, [S(k.encode(), random.choice([True, False])) for k in keys],
				needle, compar
			)
			self.assertTrue(found.value)
			self.assertEqual(index, bisect.bisect_left(keys, needle))

	def test_binary_locate_bounds(self):
		lib.binary_locate_bounds.argtypes = [
			c_void_p, c_void_p,
			c_size_t, c_size_t,
			c_void_p,
			POINTER(c_size_t), POINTER(c_size_t),
		]
		lib.binary_locate.restype = c_bool

		@CFUNCTYPE(c_int, c_char_p, POINTER(c_char_p))
		def compar(k, v):
			v = string_at(v.contents)
			if k < v:
				return -1
			elif k > v:
				return 1
			else:
				return 0

		array = (c_char_p * 5)(b'1', b'2', b'2', b'2', b'3')
		array_ptr = pointer(array)
		needle = c_char_p(b'2')
		lower = c_size_t(-1)
		upper = c_size_t(-1)
		found = lib.binary_locate_bounds(
			needle, array_ptr,
			5, sizeof(c_char_p),
			compar, byref(lower), byref(upper)
		)
		self.assertTrue(found)
		self.assertEqual(lower.value, 1)
		self.assertEqual(upper.value, 4)

		array = (c_char_p * 2)(b'1', b'3')
		array_ptr = pointer(array)
		found = lib.binary_locate_bounds(
			needle, array_ptr,
			2, sizeof(c_char_p),
			compar, byref(lower), byref(upper)
		)
		self.assertFalse(found)
		self.assertEqual(lower.value, 1)
		self.assertEqual(upper.value, 1)

		found = lib.binary_locate_bounds(
			c_char_p(b'0'), array_ptr,
			2, sizeof(c_char_p),
			compar, byref(lower), byref(upper)
		)
		self.assertFalse(found)
		self.assertEqual(lower.value, 0)
		self.assertEqual(upper.value, 0)

		found = lib.binary_locate_bounds(
			c_char_p(b'4'), array_ptr,
			2, sizeof(c_char_p),
			compar, byref(lower), byref(upper)
		)
		self.assertFalse(found)
		self.assertEqual(lower.value, 2)
		self.assertEqual(upper.value, 2)

	def test_split_memory_into_buffers(self):
		lib.split_memory_into_buffers.argtypes = [c_void_p, c_size_t]
		lib.split_memory_into_buffers.restype = None

		capacity_left = (1 << 16) * 3 // 2
		memory = create_string_buffer(capacity_left)
		start = cast(memory, c_void_p).value
		c_void_p.in_dll(lib, 'state').value = start
		state = cast(c_void_p.in_dll(lib, 'state'), POINTER(State))

		start += sizeof(State)
		capacity_left -= sizeof(State)

		if start % 8 <= 3:
			capacity_left -= 3 - start % 8
			start += 3 - start % 8
		else:
			capacity_left -= 3 + (8 - start % 8)
			start += 3 + (8 - start % 8)
		self.assertEqual(start % 8, 3)

		lib.split_memory_into_buffers(start, capacity_left)
		self.assertEqual(state.contents.buffers[0].data, start + 5)
		for i in range(0, 6):
			self.assertEqual(state.contents.buffers[i].capacity % 8, 0)
			self.assertEqual(state.contents.buffers[i].data % 8, 0)
			if i > 0:
				self.assertEqual(
					state.contents.buffers[i].data,
					state.contents.buffers[i - 1].data + state.contents.buffers[i - 1].capacity
				)

	def test_vardata_array(self):
		memory, buf = make_buffer(256)
		lib.vardata_array_make(byref(buf), 12)
		self.assertEqual(buf.size, 3 * sizeof(c_size_t) + 10 * 12)
		memory[buf.size:buf.size + 5] = (1, 2, 3, 4, 5)
		buf.size += 5

		lib.vardata_array_enlarge.argtypes = [c_void_p, c_void_p, c_size_t, c_size_t]
		lib.vardata_array_enlarge.restype = c_void_p
		vardata_start = lib.vardata_array_enlarge(byref(buf), buf.data, 1, 17)
		self.assertEqual(vardata_start, buf.data + buf.size - 17)
		self.assertEqual(buf.size, 3 * sizeof(c_size_t) + 11 * 12 + 5 + 17)
		self.assertEqual(tuple(memory[buf.size - 17 - 5:buf.size - 17]), (1, 2, 3, 4, 5))

	def test_apply_rule(self):
		lib.apply_rule.argtypes = [
			c_void_p, c_void_p, c_size_t,
			c_char_p, c_size_t,
			c_char_p, c_size_t
		]
		lib.apply_rule.restypes = None

		memory, buf = make_buffer(256)
		lib.apply_rule(
			byref(buf), cast(lib.rules, c_void_p), 5,
			'ではありません'.encode('utf-16le'), 7,
			'raw'.encode(), 3
		)

		self.assertEqual(buf.size, sizeof(Candidate) + 4 * 2 + (3 + 1 + 6))

		c = cast(buf.data, POINTER(Candidate)).contents
		self.assertEqual(c.word_length, 4)
		self.assertEqual(''.join(map(chr, c.word[:4])), 'ではない')
		self.assertEqual(c.inflection_name_length, 3 + 1 + 6)
		self.assertEqual(c.inflection_name[:10], b'raw,polite')

	def test_rule_index_bounds_for_suffix(self):
		lib.rule_index_bounds_for_suffix.argtypes = [c_char_p, c_size_t, c_void_p, c_void_p]
		lib.rule_index_bounds_for_suffix.restype = c_bool

		low = c_size_t(-1)
		high = c_size_t(-1)
		found = lib.rule_index_bounds_for_suffix('ありません'.encode('utf-16le'), 5, byref(low), byref(high))
		self.assertTrue(found)
		self.assertEqual(low.value, 0)
		self.assertEqual(high.value, 1)

		found = lib.rule_index_bounds_for_suffix('させる'.encode('utf-16le'), 3, byref(low), byref(high))
		self.assertTrue(found)
		self.assertEqual(low.value, 30)
		self.assertEqual(high.value, 33)

		found = lib.rule_index_bounds_for_suffix('せさる'.encode('utf-16le'), 3, byref(low), byref(high))
		self.assertFalse(found)

	def test_deinflect_one_word(self):
		lib.deinflect_one_word.argtypes = [
			c_void_p, c_uint,
			c_char_p, c_size_t,
			c_char_p, c_size_t,
		]
		lib.deinflect_one_word.restype = None

		memory, buf = make_buffer(256)
		lib.deinflect_one_word(
			byref(buf), 0xffffffff,
			'こき使われて'.encode('utf-16le'), 6,
			b'fake', 4
		)
		c1_size = sizeof(Candidate) + 6 * 2 + (4 + 1 + 10)
		c2_size = sizeof(Candidate) + 6 * 2 + (4 + 1 + 3)
		c3_size = sizeof(Candidate) + 7 * 2 + (4 + 1 + 9)
		self.assertEqual(buf.size, c1_size + c2_size + c3_size)

		c = cast(buf.data, POINTER(Candidate)).contents
		self.assertEqual(c.get_word(), 'こき使われつ')
		self.assertEqual(c.get_inflection_name(), 'fake,imperative')
		self.assertEqual(c.type, 0x4000)

		c = cast(buf.data + c1_size, POINTER(Candidate)).contents
		self.assertEqual(c.get_word(), 'こき使われる')
		self.assertEqual(c.get_inflection_name(), 'fake,-te')
		self.assertEqual(c.type, 0x1c)

		c = cast(buf.data + c1_size + c2_size, POINTER(Candidate)).contents
		self.assertEqual(c.get_word(), 'こき使われてる')
		self.assertEqual(c.get_inflection_name(), 'fake,masu stem')
		self.assertEqual(c.type, 0xc)

	def test_deinflect(self):
		lib.deinflect.argtypes = [c_char_p, c_size_t]
		lib.deinflect.restype = POINTER(Candidate)

		self.init_state()

		c = lib.deinflect('こき使われて'.encode('utf-16le'), 6)
		self.assertTrue(c)

		lib.candidate_next.argtypes = [POINTER(Candidate)]
		lib.candidate_next.restype = POINTER(Candidate)
		candidates = [c.contents.get_word()]
		c = lib.candidate_next(c)
		while c:
			candidates.append(c.contents.get_word())
			c = lib.candidate_next(c)

		self.assertEqual(candidates, [
			'こき使われつ',
			'こき使われる',
			'こき使われてる',
			'こき使う',
			'こき使わる',
			'こき使われつ',
		])

	def test_index_entries_cache_add_current(self):
		lib.index_entries_cache_add_current.argtypes = [c_void_p, pDictionaryIndexEntry]
		lib.index_entries_cache_add_current.restype = pDictionaryIndexEntry

		lib.index_entries_cache_clear.argtypes = [pBuffer]
		lib.index_entries_cache_clear.restype = pDictionaryIndexEntry

		memory, buf = make_buffer(512)
		it = lib.index_entries_cache_clear(byref(buf))

		initial_size = buf.size

		current = CurrentIndexEntry.in_dll(lib, 'current_index_entry')
		current.start_position_in_index = 123
		current.end_position_in_index = 456
		current.key_length = 1
		current.key = pointer(c_ushort(ord('3')))
		current.num_offsets = 3
		current.offsets = cast(pointer((c_uint * 3)(1, 2, 3)), POINTER(c_uint))
		lib.index_entries_cache_add_current(byref(buf), it)
		e1_size = 1 * sizeof(c_ushort) + 3 * sizeof(c_uint)
		self.assertEqual(buf.size, initial_size + e1_size)

		current.start_position_in_index = 321
		current.end_position_in_index = 654
		current.key_length = 2
		current.key = cast(pointer((c_ushort * 2)(ord('1'), ord('2'))), POINTER(c_ushort))
		current.num_offsets = 2
		current.offsets = cast(pointer((c_uint * 3)(4, 5)), POINTER(c_uint))
		lib.index_entries_cache_add_current(byref(buf), it)
		e2_size = 2 * sizeof(c_ushort) + 2 * sizeof(c_uint)
		self.assertEqual(buf.size, initial_size + e1_size + e2_size)

		self.assertEqual(lib.vardata_array_num_elements(byref(buf)), 2)

		e = it[0]
		self.assertEqual(e.start_position_in_index, 321)
		self.assertEqual(e.end_position_in_index, 654)
		self.assertEqual(e.key_length, 2)
		self.assertEqual(e.num_offsets, 2)

		e = it[1]
		self.assertEqual(e.start_position_in_index, 123)
		self.assertEqual(e.end_position_in_index, 456)
		self.assertEqual(e.key_length, 1)
		self.assertEqual(e.num_offsets, 3)

		return it, memory, buf

	def test_index_entries_cache_locate_entry(self):
		lib.index_entries_cache_locate_entry.argtypes = [
			pBuffer, c_char_p, c_size_t,
			POINTER(c_size_t), POINTER(c_size_t), POINTER(c_bool)
		]
		lib.index_entries_cache_locate_entry.restype = pDictionaryIndexEntry

		cache_array, memory, buf = self.test_index_entries_cache_add_current()

		low = c_size_t()
		high = c_size_t()
		found = c_bool()
		it = lib.index_entries_cache_locate_entry(
			byref(buf), '12'.encode('utf-16le'), 2,
			byref(low), byref(high), byref(found)
		)
		self.assertTrue(found)
		self.assertEqual(cast(it, c_void_p).value, cast(cache_array, c_void_p).value)

		it = lib.index_entries_cache_locate_entry(
			byref(buf), '3'.encode('utf-16le'), 1,
			byref(low), byref(high), byref(found)
		)
		self.assertTrue(found)
		self.assertEqual(cast(it, c_void_p).value, cast(cache_array, c_void_p).value + sizeof(DictionaryIndexEntry))

		low = c_size_t(0)
		high = c_size_t(-1)
		it = lib.index_entries_cache_locate_entry(
			byref(buf), '0'.encode('utf-16le'), 1,
			byref(low), byref(high), byref(found)
		)
		self.assertEqual(low.value, 0)
		self.assertEqual(high.value, 321)
		self.assertFalse(found)
		self.assertEqual(cast(it, c_void_p).value, cast(cache_array, c_void_p).value)

		low = c_size_t(-1)
		high = c_size_t(-1)
		it = lib.index_entries_cache_locate_entry(
			byref(buf), '20'.encode('utf-16le'), 3,
			byref(low), byref(high), byref(found)
		)
		self.assertEqual(low.value, 654)
		self.assertEqual(high.value, 123)
		self.assertFalse(found)
		self.assertEqual(cast(it, c_void_p).value, cast(cache_array, c_void_p).value + sizeof(DictionaryIndexEntry))

		low = c_size_t(-1)
		high = c_size_t(100500)
		it = lib.index_entries_cache_locate_entry(
			byref(buf), '4'.encode('utf-16le'), 3,
			byref(low), byref(high), byref(found)
		)
		self.assertEqual(low.value, 456)
		self.assertEqual(high.value, 100500)
		self.assertFalse(found)
		self.assertEqual(cast(it, c_void_p).value, cast(cache_array, c_void_p).value + 2 * sizeof(DictionaryIndexEntry))

	def test_dictionary_index_get_entry(self):
		self.init_state()

		it = lib.dictionary_index_get_entry(byref(test_index), 'abracadabra'.encode('utf-16le'), 11)
		self.assertFalse(it)

		for i in range(2):
			it = lib.dictionary_index_get_entry(byref(test_index), '海砂利水魚の'.encode('utf-16le'), 6)
			self.assertTrue(it)

			e = it[0]
			self.assertEqual(e.start_position_in_index, 4092)
			self.assertEqual(e.end_position_in_index, 4844)
			self.assertEqual(e.key_length, 6)
			self.assertEqual(e.num_offsets, (752 - 6 * 2) // 4)

		it = lib.dictionary_index_get_entry(byref(test_index), '擦り切れ'.encode('utf-16le'), 4)
		self.assertTrue(it)

		e = it[0]
		self.assertEqual(e.start_position_in_index, 2250)
		self.assertEqual(e.end_position_in_index, 3002)
		self.assertEqual(e.key_length, 4)
		self.assertEqual(e.num_offsets, (752 - 4 * 2) // 4)

		for i in range(2):
			it = lib.dictionary_index_get_entry(byref(test_index), '水行末'.encode('utf-16le'), 3)
			self.assertTrue(it)

			e = it[0]
			self.assertEqual(e.start_position_in_index, 3002)
			self.assertEqual(e.end_position_in_index, 4092)
			self.assertEqual(e.key_length, 3)
			self.assertEqual(e.num_offsets, (1090 - 3 * 2) // 4)

		self.assertEqual(lib.vardata_array_num_elements(lib.state_get_index_entry_buffer()), 3)

	def test_dictionary_index_offsets(self):
		lib.dictionary_index_entry_num_offsets.argtypes = [pDictionaryIndexEntry]
		lib.dictionary_index_entry_num_offsets.restype = c_size_t

		lib.dictionary_index_entry_get_offsets_iterator.argtypes = [pDictionaryIndexEntry]
		lib.dictionary_index_entry_get_offsets_iterator.restype = Iterator

		lib.offsets_iterator_read_next.argtypes = [pIterator, POINTER(c_uint), POINTER(c_uint)]
		lib.offsets_iterator_read_next.restype = c_bool

		self.init_state()

		it = lib.dictionary_index_get_entry(byref(test_index), '海砂利水魚の'.encode('utf-16le'), 6)
		self.assertTrue(it)

		self.assertEqual(lib.dictionary_index_entry_num_offsets(it), 185)

		offsets_iterator = lib.dictionary_index_entry_get_offsets_iterator(it)
		type = c_uint(-1)
		offset = c_uint(-1)
		offsets = []
		for i in range(184):
			res = lib.offsets_iterator_read_next(byref(offsets_iterator), byref(type), byref(offset))
			self.assertTrue(res)
			offsets.append((type.value, offset.value))

		res = lib.offsets_iterator_read_next(byref(offsets_iterator), byref(type), byref(offset))
		self.assertFalse(res)

		self.assertEqual(offsets[:2], [(11, 12), (0, 5)])

	def test_state_try_add_word_result(self) -> pWordResult:
		self.init_state()

		for i in range(2):
			res = lib.state_try_add_word_result(
				0x2, 12,
				'abcd'.encode('utf-16le'), 4,
				b'fake2', 5,
				123
			)
			self.assertEqual(res, i == 0)

		for i in range(2):
			res = lib.state_try_add_word_result(
				0x1, 12,
				'abc'.encode('utf-16le'), 3,
				b'fake', 4,
				123
			)
			self.assertEqual(res, i == 0)

		self.assertEqual(lib.vardata_array_num_elements(lib.state_get_word_result_buffer()), 2)
		return cast(lib.vardata_array_elements_start(lib.state_get_word_result_buffer()), pWordResult)

	def test_state_make_offsets_array_and_request_read(self):
		lib.state_make_offsets_array_and_request_read.argtypes = [c_uint]
		lib.state_make_offsets_array_and_request_read.restype = None

		@CFUNCTYPE(None, POINTER(c_uint), c_size_t, c_size_t, c_void_p, c_uint)
		def request_read_dictionary(ofs, num_words, num_names, handle, request_id):
			if num_words != 1 or num_names != 1:
				print(f'test_state_make_offsets_array_and_request_read: expected (1, 1) got ({num_words}, {num_names})')
				exit(1)
			if ofs[:2] != [123, 123]:
				print(f'test_state_make_offsets_array_and_request_read: expected (123, 123) got {ofs[:2]}')
				exit(1)

			if request_id != 4382:
				print(f'test_state_make_offsets_array_and_request_read: expected 4382 got {request_id}')
		c_void_p.in_dll(lib, 'request_read_dictionary_impl').value = cast(request_read_dictionary, c_void_p).value

		self.test_state_try_add_word_result()
		lib.state_make_offsets_array_and_request_read(4382)

	def test_sort_results(self):
		lib.sort_results.argtypes = [pWordResult, c_size_t]
		lib.sort_results.restype = None

		it = self.test_state_try_add_word_result()

		self.assertFalse(it[0].is_name)

		d1 = make_dentry()
		it[0].dentry = pointer(d1)

		d2 = make_dentry()
		d2.freq = 1
		it[1].dentry = pointer(d2)

		lib.sort_results(it, 2)

		self.assertTrue(it[0].is_name)

	def test_state_sort_and_limit_word_results(self):
		lib.state_sort_and_limit_word_results.restype = None

		self.init_state()

		added = 0
		while added < 40:
			success = lib.state_try_add_word_result(
				random.choice([0x1, 0x2]), random.randrange(1, 13),
				'abc'.encode('utf-16le'), 3,
				b'f', 1,
				random.randrange(2**24)
			)
			if success:
				added += 1

		it = cast(lib.vardata_array_elements_start(lib.state_get_word_result_buffer()), pWordResult)
		for i in range(40):
			it[i].dentry = pointer(make_dentry())

		lib.state_sort_and_limit_word_results()
		self.assertEqual(lib.vardata_array_num_elements(lib.state_get_word_result_buffer()), 32)

	def test_word_result_get_inflection_name(self):
		lib.word_result_get_inflection_name_length.argtypes = [c_void_p]
		lib.word_result_get_inflection_name_length.restype = c_size_t

		lib.word_result_get_inflection_name.argtypes = [c_void_p]
		lib.word_result_get_inflection_name.restype = c_char_p

		self.test_state_try_add_word_result()

		it = lib.state_get_word_result_iterator()

		self.assertEqual(lib.word_result_get_inflection_name_length(it.current), 4)
		self.assertEqual(lib.word_result_get_inflection_name(it.current)[:4], b'fake')

		lib.word_result_iterator_next(byref(it))

		self.assertEqual(lib.word_result_get_inflection_name_length(it.current), 5)
		self.assertEqual(lib.word_result_get_inflection_name(it.current)[:5], b'fake2')

		lib.word_result_iterator_next(byref(it))
		self.assertEqual(it.current, it.end)

	def test_word_search(self):
		lib.word_search.argtypes = [
			c_uint, c_size_t,
			c_char_p, c_size_t,
			c_uint,
			c_char_p, c_size_t
		]
		lib.word_search.restype = c_bool
		self.init_state()

		res = lib.word_search(0x1, 12, 'かける'.encode('utf-16le'), 3, 0, b'fake', 4)
		self.assertTrue(res)

		it = lib.state_get_word_result_iterator()
		self.assertEqual((it.end - it.current) // sizeof(WordResult), 6)
		current = cast(it.current, pWordResult)

		offsets = T.get_offsets('かける')
		for i in range(6):
			wr = current[i]
			self.assertFalse(wr.is_name)
			self.assertEqual(wr.match_utf16_length, 12)
			self.assertEqual(wr.key_length, 3)
			self.assertEqual(wr.inflection_name_length, 4)
			self.assertIn(wr.offset, offsets)

		res = lib.word_search(0x1, 12, 'かける'.encode('utf-16le'), 3, 0, b'fake', 4)
		self.assertFalse(res)

		lib.state_get_word_result_buffer().contents.size = 0

		res = lib.word_search(0x1, 12, 'かける'.encode('utf-16le'), 3, 0x2000, b'fake', 4)
		self.assertTrue(res)

	def test_input_search(self):
		lib.input_search.argtypes = [pInput, c_uint]
		lib.input_search.restype = c_size_t

		self.init_state()

		input = Input(InputData(*map(ord, 'かけられて')), InputLengthMapping(), 5)
		res = lib.input_search(byref(input), 0x1)
		self.assertEqual(res, 5)

		it = lib.state_get_word_result_iterator()
		self.assertEqual((it.end - it.current) // sizeof(WordResult), 42)
		current = cast(it.current, pWordResult)

		offsets = T.get_offsets('かける')
		for i in range(42):
			wr = current[i]
			self.assertFalse(wr.is_name)
			offsets.discard(wr.offset)
		self.assertEqual(len(offsets), 0)

		res = lib.input_search(byref(input), 0x1)
		self.assertEqual(res, 0)

	def test_word_search_finish(self):
		lib.word_search_finish.argtypes = [pBuffer]
		lib.word_search_finish.restype = c_bool

		self.test_state_try_add_word_result()

		memory, buf = make_buffer(1024)

		s = dictionary_line.encode()
		memory[0] = len(s)
		memory[2:2 + len(s)] = s

		memory[2 + len(s)] = len(s)
		memory[2 + len(s) + 2:2 + len(s) + 2 + len(s)] = s

		buf.size = 2 + len(s) + 2 + len(s)

		self.assertTrue(lib.word_search_finish(byref(buf)))

	def test_search_start(self):
		lib.search_start.argtypes = [c_size_t]
		lib.search_start.restype = c_size_t

		self.init_state()

		offsets = T.get_offsets('かける')
		@CFUNCTYPE(None, POINTER(c_uint), c_size_t, POINTER(c_ubyte), c_void_p)
		def request_read_dictionary(ofs, num_ofs, data, handle):
			ofs = set(ofs[:num_ofs])
			if offsets.issuperset(ofs):
				print(f'expected {offsets} got {ofs}')
				exit(1)
		c_void_p.in_dll(lib, 'request_read_dictionary_impl').value = cast(request_read_dictionary, c_void_p).value

		for i, c in enumerate('かける'):
			self.state.contents.input.data[i] = ord(c)
		self.assertEqual(lib.search_start(3), 3)

	def test_append(self):
		lib.append.argtypes = [pBuffer, c_char_p, c_size_t]
		lib.append.restype = None

		memory, buf = make_buffer(256)
		lib.append(byref(buf), b'123', 2)
		self.assertEqual(buf.size, 2)
		self.assertEqual(memory[:2], b'12')

	def test_append_char(self):
		lib.append_char.argtypes = [pBuffer, c_char]
		lib.append_char.restype = None

		memory, buf = make_buffer(256)
		lib.append_char(byref(buf), ord('\\'))
		self.assertEqual(buf.size, 1)
		self.assertEqual(memory[0], b'\\')

	def test_append_uint(self):
		lib.append_uint.argtypes = [pBuffer, c_uint]
		lib.append_uint.restype = None

		memory, buf = make_buffer(256)
		lib.append_uint(byref(buf), 812734)
		self.assertEqual(buf.size, 6)
		self.assertEqual(memory[:6], b'812734')

	def test_try_render_inflection_info(self):
		lib.try_render_inflection_info.argtypes = [pBuffer, pWordResult]
		lib.try_render_inflection_info.restype = None

		wr = self.test_state_try_add_word_result()

		memory, buf = make_buffer(256)

		lib.try_render_inflection_info(byref(buf), wr)
		self.assertTrue(memory[:buf.size].strip())

	def test_render_reading(self):
		lib.render_reading.argtypes = [pBuffer, pReading, c_bool, c_bool]
		lib.render_reading.restype = None

		memory, buf = make_buffer(256)
		reading = Reading(b'123', 3, True)
		for a, b in [(False, False), (False, True), (True, False), (True, True)]:
			lib.render_reading(byref(buf), byref(reading), a, b)
			self.assertTrue(memory[:buf.size].strip())
			buf.size = 0

	def test_render_all_readings(self):
		lib.render_all_readings.argtypes = [pBuffer, pDentry, c_bool]
		lib.render_all_readings.restype = None

		memory, buf = make_buffer(256)
		d = make_dentry()
		for flag in [False, True]:
			lib.render_all_readings(byref(buf), byref(d), flag)
			self.assertTrue(memory[:buf.size].strip())
			buf.size = 0

	def test_render_kanji_group(self):
		lib.render_kanji_group.argtypes = [pBuffer, pWordResult, pDentry, pKanjiGroup, c_bool, c_bool]
		lib.render_kanji_group.restype = None

		self.init_state()

		memory, buf = make_buffer(256)
		wr = self.make_word_result()
		for a, b, i in itertools.product([False, True], [False, True], [0, 1]):
			kg = cast(
				c_void_p(
					cast(wr.contents.dentry.contents.kanji_groups, c_void_p).value + sizeof(KanjiGroup) * i
				),
				pKanjiGroup
			)
			lib.render_kanji_group(byref(buf), wr, wr.contents.dentry, kg, a, b)
			self.assertTrue(memory[:buf.size].strip())
			buf.size = 0

	def test_render_readings_only_dentry_readings(self):
		lib.render_readings_only_dentry_readings.argtypes = [pBuffer, pWordResult, pDentry]
		lib.render_readings_only_dentry_readings.restype = None

		self.init_state()

		memory, buf = make_buffer(256)
		wr = self.make_word_result()
		lib.render_readings_only_dentry_readings(byref(buf), wr, wr.contents.dentry)
		self.assertTrue(memory[:buf.size].strip())

	def test_render_sense_group(self):
		lib.render_sense_group.argtypes = [pBuffer, pSenseGroup, c_bool]
		lib.render_sense_group.restype = None

		self.init_state()

		memory, buf = make_buffer(256)
		d = make_dentry()
		for flag in [False, True]:
			lib.render_sense_group(byref(buf), d.sense_groups, flag)
			self.assertTrue(memory[:buf.size].strip())
			buf.size = 0

	def test_render_dentry(self):
		lib.render_dentry.argtypes = [pBuffer, pWordResult]
		lib.render_dentry.restype = None

		self.init_state()

		memory, buf = make_buffer(1024)
		wr = self.make_word_result()
		lib.render_dentry(byref(buf), wr)
		self.assertTrue(memory[:buf.size].strip())

	def test_render_entry(self):
		lib.render_entry.argtypes = [pBuffer, pWordResult, c_bool]
		lib.render_entry.restype = None

		self.init_state()

		memory, buf = make_buffer(1024)
		wr = self.make_word_result()
		for flag in [False, True]:
			lib.render_entry(byref(buf), wr, flag)
			self.assertTrue(memory[:buf.size].strip())
			buf.size = 0

	def test_render_entries(self):
		lib.render_entries.argtypes = [pBuffer]
		lib.render_entries.restype = None

		wr = self.test_state_try_add_word_result()
		d = make_dentry()
		wr[0].dentry = pointer(d)
		wr[1].dentry = pointer(d)

		memory, buf = make_buffer(2048)
		lib.render_entries(byref(buf))
		self.assertTrue(memory[:buf.size].strip())
