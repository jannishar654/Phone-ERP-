"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { getCatalogItems, createCatalogItem, updateCatalogItemStatus } from "@/lib/api";

interface CatalogItem {
  id: string;
  canonical_name: string;
  display_name: string;
  english_name?: string;
  base_price: number;
  unit: string;
  category?: string;
  active: boolean;
  in_stock: boolean;
  aliases: string[];
}

export default function CatalogPage() {
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [newItemName, setNewItemName] = useState("");
  const [newCanonicalName, setNewCanonicalName] = useState("");
  const [newEnglishName, setNewEnglishName] = useState("");
  const [newItemPrice, setNewItemPrice] = useState("");
  const [newItemUnit, setNewItemUnit] = useState("kg");
  const [newCategory, setNewCategory] = useState("");
  const [newAliases, setNewAliases] = useState("");

  useEffect(() => {
    fetchItems();
  }, []);

  const fetchItems = async () => {
    try {
      setLoading(true);
      setError("");
      const data = await getCatalogItems();
      setItems(data || []);
    } catch (err: any) {
      setError(err.message || "Failed to load catalog items (mock behavior active if offline).");
    } finally {
      setLoading(false);
    }
  };

  const addItem = async () => {
    if (!newItemName || !newCanonicalName || !newItemPrice) {
      setError("Display Name, Canonical Name, and Base Price are required.");
      return;
    }
    
    try {
      setError("");
      const payload = {
        display_name: newItemName,
        canonical_name: newCanonicalName.toLowerCase(),
        english_name: newEnglishName || null,
        base_price: parseFloat(newItemPrice),
        unit: newItemUnit,
        category: newCategory || null,
        aliases: newAliases.split(",").map(s => s.trim()).filter(Boolean),
      };
      
      const createdItem = await createCatalogItem(payload);
      setItems([...items, createdItem]);
      
      setNewItemName("");
      setNewCanonicalName("");
      setNewEnglishName("");
      setNewItemPrice("");
      setNewCategory("");
      setNewAliases("");
    } catch (err: any) {
      setError(err.message || "Failed to create catalog item.");
    }
  };

  const toggleStatus = async (id: string, currentStatus: boolean, field: 'active' | 'in_stock') => {
    try {
      await updateCatalogItemStatus(id, { [field]: !currentStatus });
      setItems(items.map(it => it.id === id ? { ...it, [field]: !currentStatus } : it));
    } catch (err: any) {
      setError(err.message || `Failed to update ${field}.`);
    }
  };

  if (loading) return <div className="p-8 text-center text-gray-500">Loading catalog...</div>;

  return (
    <div className="min-h-screen bg-gray-50 pb-24">
      <header className="bg-white border-b px-4 py-3 sticky top-0 z-10">
        <div className="flex items-center gap-3">
          <Link href="/dashboard" className="p-2 -ml-2 rounded-full hover:bg-gray-100 text-gray-600 transition-colors text-sm font-bold">
            &larr; Back
          </Link>
          <h1 className="text-lg font-semibold text-gray-900">Shop Catalog</h1>
        </div>
      </header>

      <main className="p-4 max-w-lg mx-auto">
        {error && <div className="bg-red-50 text-red-600 p-3 rounded-lg mb-4 text-sm">{error}</div>}

        <div className="bg-white p-4 rounded-xl shadow-sm border mb-6">
          <h2 className="font-medium mb-3">Add New Item</h2>
          <div className="flex flex-col gap-3">
            <input 
              type="text" 
              placeholder="Display Name (e.g. Sugar / Chini)" 
              className="border p-2 rounded text-sm"
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
            />
            <input 
              type="text" 
              placeholder="Canonical Name (e.g. sugar)" 
              className="border p-2 rounded text-sm"
              value={newCanonicalName}
              onChange={(e) => setNewCanonicalName(e.target.value)}
            />
            <input 
              type="text" 
              placeholder="English Name (Optional)" 
              className="border p-2 rounded text-sm"
              value={newEnglishName}
              onChange={(e) => setNewEnglishName(e.target.value)}
            />
            
            <div className="flex gap-2">
              <input 
                type="number" 
                placeholder="Base Price" 
                className="border p-2 rounded w-full text-sm"
                value={newItemPrice}
                onChange={(e) => setNewItemPrice(e.target.value)}
              />
              <select className="border p-2 rounded w-32 text-sm" value={newItemUnit} onChange={(e) => setNewItemUnit(e.target.value)}>
                <option value="kg">kg</option>
                <option value="litre">litre</option>
                <option value="packet">packet</option>
                <option value="carton">carton</option>
                <option value="dozen">dozen</option>
                <option value="piece">piece</option>
              </select>
            </div>

            <input 
              type="text" 
              placeholder="Category (Optional)" 
              className="border p-2 rounded text-sm"
              value={newCategory}
              onChange={(e) => setNewCategory(e.target.value)}
            />

            <input 
              type="text" 
              placeholder="Aliases (comma-separated, e.g. chini, aalu)" 
              className="border p-2 rounded text-sm"
              value={newAliases}
              onChange={(e) => setNewAliases(e.target.value)}
            />

            <button 
              onClick={addItem}
              className="bg-blue-600 text-white p-2 rounded font-medium flex items-center justify-center gap-2 hover:bg-blue-700 mt-2"
            >
              + Add Item
            </button>
          </div>
        </div>

        <div className="space-y-3">
          <h2 className="font-medium text-gray-700">Current Items ({items.length})</h2>
          {items.length === 0 ? (
            <p className="text-gray-500 text-sm italic">No items in catalog yet.</p>
          ) : (
            items.map(item => (
              <div key={item.id} className={`bg-white p-4 rounded-xl shadow-sm border flex flex-col gap-2 ${!item.active ? 'opacity-50' : ''}`}>
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="font-medium text-gray-900">{item.display_name}</h3>
                    <p className="text-sm text-gray-500">₹{item.base_price} / {item.unit}</p>
                    <p className="text-xs text-gray-400 mt-1">ID: {item.canonical_name}</p>
                    {item.aliases && item.aliases.length > 0 && (
                      <p className="text-xs text-gray-400">Aliases: {item.aliases.join(', ')}</p>
                    )}
                  </div>
                  <div className="flex flex-col gap-2">
                    <button onClick={() => toggleStatus(item.id, item.in_stock, 'in_stock')} className={`text-xs px-2 py-1 rounded ${item.in_stock ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'}`}>
                      {item.in_stock ? 'In Stock' : 'Out of Stock'}
                    </button>
                    <button onClick={() => toggleStatus(item.id, item.active, 'active')} className={`text-xs px-2 py-1 rounded ${item.active ? 'bg-gray-100 text-gray-700' : 'bg-red-100 text-red-700'}`}>
                      {item.active ? 'Active' : 'Inactive'}
                    </button>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </main>
    </div>
  );
}
