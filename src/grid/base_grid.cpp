#pragma once

#include "stdafx.h"

#include "grid_spec.cpp"
#include "sparse_grid.cpp"




template<typename spec_t, typename sub_t>
class BaseGrid {
    /*
    abstract base class using CRTP, or compile-time polymorphism
    for code reuse between point and object grids

    Requirements on sub_t:
        self.grid, type SparseGrid
        self.cell_id, type ndarray<fixed_t>


    cant put any state here, since it messes with initialization order
    */
public:
    typedef BaseGrid<spec_t, sub_t>			base_t;
    typedef typename spec_t::real_t         real_t;
	typedef typename spec_t::index_t		index_t;
	typedef typename spec_t::fixed_t		fixed_t;

	typedef typename spec_t::box_t			box_t;
	typedef typename spec_t::vector_t		vector_t;
	typedef typename spec_t::cell_t			cell_t;
	typedef erow<index_t, 2>                pair_t;


public:
    sub_t&                                  self;
	const spec_t				            spec;
    const index_t                           n_objects;

	auto get_permutation()  const { return self.grid.permutation; }

public:
    BaseGrid(
        const spec_t spec,
        const index_t n_objects) :
        self        (*static_cast<sub_t*>(this)),
        spec        (spec),
        n_objects   (n_objects)
    {
    }

    // ndarray of unique pairs from vector of non-unique pairs
    auto unique_pairs(std::vector<pair_t>& pairs) const {
        auto pair_order = [&](const pair_t& i, const pair_t& j) {
            const pair_t d = i - j;
            return d(0) * self.n_objects + d(1) < 0;
        };
        auto pair_not_equal = [](const pair_t& i, const pair_t& j) {
            return (i != j).any();
        };
        boost::sort(pairs, pair_order);

        std::vector<pair_t> unique_pairs(0);
        for (pair_t& p : pairs | adjacent_filtered(pair_not_equal))
            unique_pairs.push_back(p);

	    index_t n_pairs(unique_pairs.size());
        ndarray<index_t, 2> output({ n_pairs, 2});

        for (index_t p : irange(0, n_pairs)) {
            output[p][0] = unique_pairs[p][0];
            output[p][1] = unique_pairs[p][1];
        }
        return output;
    }

	// intersect two sparse grids, to get shared occupied cells
	template<typename other_t>
	std::vector<fixed_t> intersect_cells(const other_t& other) const {
	    if (self.spec == other.spec)
	        throw python_exception("Grids to be intersected do not have identical specifications");

        // for each intersection of cell hashes
	    std::vector<fixed_t> intersection;
        boost::range::set_intersection(
            self.cell_id.range(),
            other.cell_id.range(),
            std::back_inserter(intersection)
        );
        return intersection;
	}

};
