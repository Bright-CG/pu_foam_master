@extends('layouts.app')

@section('title', 'Stock Items')

@section('content')
<div class="container-fluid p-0">
    <!-- Header -->
    <div class="d-flex flex-column flex-md-row justify-content-between align-items-md-center gap-3 mb-4">
        <div>
            <div class="d-flex align-items-center gap-2 mb-1">
                <h2 class="fw-bold text-dark mb-0">Stock Items &amp; Inventory</h2>
                <span class="badge bg-secondary-subtle text-secondary border px-2 py-1">
                    {{ number_format($items->total()) }} Items
                </span>
            </div>
            <div class="text-muted small">
                Product catalog, unit of measures, stock quantities, and valuation
            </div>
        </div>

        <div class="d-flex align-items-center gap-2 no-print">
            <button onclick="window.print()" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-2">
                <i class="fa-solid fa-print"></i>
                <span>Print Stock List</span>
            </button>
        </div>
    </div>

    <!-- Search & Filter Card -->
    <div class="card shadow-sm border mb-4 no-print">
        <div class="card-body p-3">
            <form action="{{ route('inventory.index') }}" method="GET" class="search-form row g-2 align-items-center">
                <!-- Search Keyword -->
                <div class="col-12 col-md-5 col-lg-4">
                    <div class="input-group">
                        <span class="input-group-text bg-white border-end-0 text-muted">
                            <i class="fa-solid fa-magnifying-glass"></i>
                        </span>
                        <input type="text" 
                               name="search" 
                               class="form-control border-start-0 ps-0" 
                               placeholder="Search by code, description, category..." 
                               value="{{ request('search') }}">
                    </div>
                </div>

                <!-- Category Dropdown Filter -->
                <div class="col-12 col-sm-6 col-md-4 col-lg-3">
                    <select name="category" class="form-select">
                        <option value="">All Categories</option>
                        @foreach($categories as $cat)
                            <option value="{{ $cat }}" {{ request('category') == $cat ? 'selected' : '' }}>
                                {{ $cat }}
                            </option>
                        @endforeach
                    </select>
                </div>

                <!-- Action Buttons -->
                <div class="col-auto d-flex gap-2">
                    <button type="submit" class="btn btn-emerald px-3">
                        <i class="fa-solid fa-filter me-1"></i> Filter
                    </button>
                    @if(request('search') || request('category'))
                        <a href="{{ route('inventory.index') }}" class="btn btn-outline-secondary px-3">
                            <i class="fa-solid fa-xmark me-1"></i> Clear
                        </a>
                    @endif
                </div>

                <div class="col text-end d-none d-lg-block text-muted small">
                    Showing {{ $items->firstItem() ?? 0 }} to {{ $items->lastItem() ?? 0 }} of {{ $items->total() }} items
                </div>
            </form>
        </div>
    </div>

    <!-- Inventory Table Card -->
    <div class="card shadow-sm border">
        <div class="card-body p-0">
            <div class="table-responsive">
                <table class="table table-striped table-hover align-middle mb-0">
                    <thead>
                        <tr>
                            <th style="width: 140px;">Item Code</th>
                            <th>Description</th>
                            <th style="width: 100px;">UOM</th>
                            <th style="width: 160px;">Category</th>
                            <th class="text-end" style="width: 140px;">Qty on Hand</th>
                            <th class="text-end" style="width: 140px;">Unit Cost (₦)</th>
                            <th class="text-end" style="width: 160px;">Valuation (₦)</th>
                        </tr>
                    </thead>
                    <tbody>
                        @forelse($items as $item)
                            @php
                                $qty = legacy_amount($item->stock_qty);
                                $cost = legacy_amount($item->unit_cost);
                                $valuation = $qty * $cost;
                            @endphp
                            <tr>
                                <td>
                                    <span class="badge badge-archive font-mono">{{ $item->item_code }}</span>
                                </td>
                                <td>
                                    <div class="fw-semibold text-dark">{{ $item->description }}</div>
                                </td>
                                <td>
                                    <span class="badge bg-light text-secondary border font-mono small">
                                        {{ $item->uom ?: 'Units' }}
                                    </span>
                                </td>
                                <td>
                                    <span class="text-secondary small">
                                        {{ $item->category ?: 'General' }}
                                    </span>
                                </td>
                                <td class="text-end font-mono fw-semibold {{ $qty > 0 ? 'text-dark' : 'text-muted' }}">
                                    {{ number_format($qty, 2) }}
                                </td>
                                <td class="text-end font-mono text-secondary">
                                    {{ number_format($cost, 2) }}
                                </td>
                                <td class="text-end font-mono fw-bold {{ $valuation > 0 ? 'text-success' : 'text-muted' }}">
                                    {{ number_format($valuation, 2) }}
                                </td>
                            </tr>
                        @empty
                            <tr>
                                <td colspan="7" class="text-center py-5 text-muted">
                                    <i class="fa-solid fa-boxes-stacked fs-1 d-block mb-3 text-secondary"></i>
                                    <h5>No Stock Items Found</h5>
                                    <p class="small mb-0">No inventory records match your search or category filters.</p>
                                </td>
                            </tr>
                        @endforelse
                    </tbody>
                </table>
            </div>
        </div>

        @if($items->hasPages())
            <div class="card-footer bg-white border-top p-3 d-flex flex-column flex-md-row justify-content-between align-items-center gap-2 no-print">
                <div class="text-muted small">
                    Showing {{ $items->firstItem() }} to {{ $items->lastItem() }} of {{ $items->total() }} stock items
                </div>
                <div>
                    {{ $items->links() }}
                </div>
            </div>
        @endif
    </div>
</div>
@endsection
