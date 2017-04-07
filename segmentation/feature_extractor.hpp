#pragma once

#include <vector>
#include <dlib/matrix.h>
#include <cstdint>
#include <utility>

inline char character_class(char16_t character)
{
	return (character >= 0x4e00 && character <= 0x9fa5)
		? 'K'
		: (character >= 0x3040 && character <= 0x309f)
		? 'h'
		: (character >= 0x30a1 && character <= 0x30fe)
		? 'k'
		: 'm';
}

inline std::pair<uint32_t, uint32_t> bigram(unsigned long label1, char class1, unsigned long label2, char class2)
{
	uint32_t key = label1 << 24;
	key |= uint32_t(class1) << 16;
	key |= uint32_t(label2) << 8;
	key |= uint32_t(class2);
	return std::make_pair(0, key);
}

inline std::pair<uint32_t, uint32_t> feature(uint32_t tag, char16_t character)
{
	return std::make_pair(tag << 24, character);
}

inline std::pair<uint32_t, uint32_t> feature(uint32_t tag, char16_t char1, char16_t char2)
{
	return std::make_pair(tag << 24, (uint32_t(char1) << 16) | char2);
}

inline std::pair<uint32_t, uint32_t> feature(uint32_t tag, char16_t char1, char16_t char2, char16_t char3)
{
	return std::make_pair((tag << 24) | char1, (uint32_t(char2) << 16) | char3);
}

inline std::pair<uint32_t, uint32_t> feature(uint32_t tag, char character_class)
{
	return std::make_pair(tag << 24, character_class);
}

inline std::pair<uint32_t, uint32_t> feature(uint32_t tag, char class1, char class2)
{
	return std::make_pair(tag << 24, (uint32_t(class1) << 8) | uint8_t(class2));
}

inline std::pair<uint32_t, uint32_t> feature(uint32_t tag, char class1, char class2, char class3)
{
	return std::make_pair(tag << 24, (uint32_t(class1) << 16) | (uint32_t(class2) << 8) | uint8_t(class3));
}

template<typename feature_index>
struct feature_extractor
{
	typedef std::vector<char16_t> sequence_type;

	unsigned long num_features() const
	{
		return index->num_features();
	}

	unsigned long order() const
	{
		return 1; // First-order model - looks only at previous label
	}

	unsigned long num_labels() const
	{
		return 2; // S(tart) and M(iddle)
	}

	template <typename feature_setter, typename EXP>
	void get_features (feature_setter& set_feature,
		const sequence_type& x,	const dlib::matrix_exp<EXP>& y,
		unsigned long position) const
	{
		char16_t current_character = x[position];
		char current_class = character_class(current_character);

		char16_t previous_character = 0, next_character = 0;
		char previous_class = 0, next_class = 0;

		if (position > 0)
		{
			previous_character = x[position - 1];
			previous_class = character_class(previous_character);

			set_feature(index->get(bigram(y(1), previous_class, y(0), current_class)));
//			set_feature(index->get(bigram(y(1), '\0', y(0), '\0')));

			set_feature(index->get(feature(0b001000, previous_character)));
			set_feature(index->get(feature(0b001100, previous_character, current_character)));

			set_feature(index->get(feature(0b101000, previous_class)));
			set_feature(index->get(feature(0b101100, previous_class, current_class)));

			if (position > 1)
			{
				char16_t previous_previous_character = x[position - 1];
				char previous_previous_class = character_class(previous_previous_character);

				set_feature(index->get(feature(0b010000, previous_previous_character)));
				set_feature(index->get(feature(0b011000, previous_previous_character,
					previous_character)));
				set_feature(index->get(feature(0b011100, previous_previous_character,
					previous_character, current_character)));

				set_feature(index->get(feature(0b110000, previous_previous_class)));
				set_feature(index->get(feature(0b111000, previous_previous_class,
					previous_class)));
				set_feature(index->get(feature(0b111100, previous_previous_class,
					previous_class, current_class)));
			}
		}

		set_feature(index->get(feature(0b000100, current_character)));
		set_feature(index->get(feature(0b100100, current_class)));

		if (position + 1 < x.size())
		{
			next_character = x[position + 1];
			next_class = character_class(next_character);

			set_feature(index->get(feature(0b000010, next_character)));
			set_feature(index->get(feature(0b000110, current_character, next_character)));

			set_feature(index->get(feature(0b100010, next_class)));
			set_feature(index->get(feature(0b100110, current_class, next_class)));

			if (position + 2 < x.size())
			{
				char16_t next_next_character = x[position - 1];
				char next_next_class = character_class(next_next_character);

				set_feature(index->get(feature(0b000001, next_next_character)));
				set_feature(index->get(feature(0b000011, next_character,
					next_next_character)));
				set_feature(index->get(feature(0b000111, current_character,
					next_character, next_next_character)));

				set_feature(index->get(feature(0b100001, next_next_class)));
				set_feature(index->get(feature(0b100011, next_class,
					next_next_class)));
				set_feature(index->get(feature(0b100111, current_class,
					next_class, next_next_class)));
			}
		}

		if (position > 0 and position + 1 < x.size())
		{
			set_feature(index->get(feature(0b001110, previous_character, current_character,
				next_character)));
			set_feature(index->get(feature(0b101110, previous_class, current_class,
				next_class)));
		}
	}

	feature_extractor(const std::shared_ptr<feature_index>& index)
		: index(index)
	{}

	feature_extractor()
		: index(new feature_index)
	{}

	std::shared_ptr<feature_index> index;
};
