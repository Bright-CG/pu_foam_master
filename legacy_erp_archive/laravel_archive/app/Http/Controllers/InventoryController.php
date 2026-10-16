<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;

class InventoryController extends Controller
{
    public function index(Request $request)
    {
        $query = DB::table('stock_items');

        if ($request->filled('search')) {
            $q = '%' . $request->search . '%';
            $query->where(function ($qb) use ($q) {
                $qb->where('item_code', 'like', $q)
                   ->orWhere('description', 'like', $q)
                   ->orWhere('category', 'like', $q);
            });
        }

        if ($request->filled('category')) {
            $query->where('category', $request->category);
        }

        $items = $query->orderBy('item_code')->paginate(80)->withQueryString();

        $categories = DB::table('stock_items')
            ->distinct()
            ->pluck('category')
            ->filter()
            ->sort()
            ->values();

        return view('inventory.index', compact('items', 'categories'));
    }
}
