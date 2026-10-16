<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Schema;

class SupplierController extends Controller
{
    public function index(Request $request)
    {
        $query = DB::table('suppliers');
        $hasStatements = Schema::hasTable('supplier_statement_lines');

        if ($request->filled('search')) {
            $q = '%' . $request->search . '%';
            $query->where(function ($qb) use ($q) {
                $qb->where('id', 'like', $q)
                   ->orWhere('name', 'like', $q)
                   ->orWhere('phone', 'like', $q);
            });
        }

        $suppliers = $query->select('suppliers.*');

        if ($hasStatements) {
            $suppliers->selectSub(function ($qb) {
                $qb->from('supplier_statement_lines')
                    ->selectRaw('COUNT(*)')
                    ->whereColumn('supplier_statement_lines.supplier_id', 'suppliers.id');
            }, 'statement_line_count');
        }

        $suppliers->selectSub(function ($qb) {
            $qb->from('supplier_transactions')
                ->selectRaw('COUNT(*)')
                ->whereColumn('supplier_transactions.supplier_id', 'suppliers.id');
        }, 'inquiry_transaction_count');

        $suppliers = $suppliers
            ->orderBy('name')
            ->paginate(50)
            ->withQueryString();

        return view('suppliers.index', compact('suppliers', 'hasStatements'));
    }

    public function show(Request $request, string $id)
    {
        $supplier = DB::table('suppliers')->where('id', $id)->first();

        if (!$supplier) {
            abort(404, 'Supplier not found.');
        }

        $hasStatements = Schema::hasTable('supplier_statement_lines');
        $useStatement = $hasStatements
            && DB::table('supplier_statement_lines')->where('supplier_id', $id)->exists();

        if ($useStatement) {
            $transQuery = DB::table('supplier_statement_lines')
                ->where('supplier_id', $id)
                ->orderByRaw('CAST(line_no AS INTEGER) ASC')
                ->orderBy('id', 'asc');

            if ($request->filled('from_date')) {
                $transQuery->where('trans_date', '>=', $request->from_date);
            }
            if ($request->filled('to_date')) {
                $transQuery->where('trans_date', '<=', $request->to_date);
            }
            if ($request->filled('type')) {
                $transQuery->where('trans_type', $request->type);
            }

            $transactions = $transQuery->paginate(100)->withQueryString();

            $transTypes = DB::table('supplier_statement_lines')
                ->where('supplier_id', $id)
                ->distinct()
                ->pluck('trans_type')
                ->filter()
                ->sort()
                ->values();

            $reportPeriod = DB::table('supplier_statement_lines')
                ->where('supplier_id', $id)
                ->select('report_from_date', 'report_to_date')
                ->orderByDesc('id')
                ->first();

            return view('suppliers.show', [
                'supplier' => $supplier,
                'transactions' => $transactions,
                'transTypes' => $transTypes,
                'ledgerSource' => 'statement',
                'reportPeriod' => $reportPeriod,
            ]);
        }

        $transQuery = DB::table('supplier_transactions')
            ->where('supplier_id', $id)
            ->orderBy('trans_date', 'asc')
            ->orderBy('trans_no', 'asc')
            ->orderBy('id', 'asc');

        if ($request->filled('from_date')) {
            $transQuery->where('trans_date', '>=', $request->from_date);
        }
        if ($request->filled('to_date')) {
            $transQuery->where('trans_date', '<=', $request->to_date);
        }

        $transactions = $transQuery->paginate(100)->withQueryString();

        $transTypes = DB::table('supplier_transactions')
            ->where('supplier_id', $id)
            ->distinct()
            ->pluck('trans_type')
            ->filter()
            ->sort()
            ->values();

        return view('suppliers.show', [
            'supplier' => $supplier,
            'transactions' => $transactions,
            'transTypes' => $transTypes,
            'ledgerSource' => 'inquiry',
            'reportPeriod' => null,
        ]);
    }
}
