
#pragma once

#include <functional>

#include <boost/tuple/tuple.hpp>


#include "ndarray.cpp"
#include "linalg.cpp"


//used for hashing calcs
const int3 primes(73856093, 19349663, 83492791);


template<class key_type, class value_type, int NDim>
class HashMap {

//	typedef key_type key_type;

//    typedef int32 key_type_scalar;
	typename typedef key_type::Scalar key_type_scalar;

    const int n_items;                  // number of items
	const int n_entries;                // number of entries
	ndarray<2, key_type_scalar> keys;   // voxel coordinates uniquely identifying a bucket
	ndarray<1, value_type>      values; // bucket description, or where to look in pivot array

public:
    // construct by zipping keys and values range
    template<typename items_range>
	HashMap(const int n_items, const items_range& items):
	    n_items(n_items),
	    n_entries(init_entries()),
		keys({n_entries, NDim}),
		values({n_entries})
	{
		//mark grid as unoccupied
		fill(values, -1);
        for (auto item : items)
            write(boost::get<0>(item), boost::get<1>(item));
	}

	inline const value_type operator[](const key_type& key) const
	{
	    const auto _keys = keys.view<const key_type>();
		int entry = get_hash(key);			//hash guess
		while (true)						//find the right entry
		{
			if ((_keys[entry] == key).all())
			    return values[entry];	                // we found it; this should be the most common code path
			if (values[entry] == -1) return -1;	    	// if we didnt find it yet by now, we never will
			entry = (entry + 1) & (n_entries - 1);		// circular increment
		}
	}

private:
	inline void write(const key_type& key, const value_type value)
	{
	    auto _keys = keys.view<key_type>();
		int entry = get_hash(key);				// get entry initial guess
		while (true)                            // find an empty entry
		{
			if (values[entry] == -1) break;         // found an empty entry
			entry = (entry + 1) & (n_entries - 1);	// circular increment
		}
		values[entry] = value;
		_keys[entry] = key;
	}

	inline int get_hash(const key_type& key) const
	{
		const int3 c = key.cast<int>() * primes;
		return c.redux(std::bit_xor<int>()) & (n_entries - 1);
	}

	int init_entries() const
	{
		//calc number of entries in hashmap. hashmap should have twice the number of items, at mimimum.
		int entries = 64;
		while (entries < n_items * 2) entries <<= 1;
		return entries;
	}
};

//// for checking if it matters anything in terms of performance
//class StdMap : public std::map
//{
//
//};
