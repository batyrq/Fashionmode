import { supabase } from "./auth.js";

export async function listSavedOutfits() {
  const { data, error } = await supabase
    .from("saved_outfits")
    .select("id, name, style, occasion, total_price, currency, outfit_payload, source_type, created_at")
    .neq("source_type", "favorite_product")
    .order("created_at", { ascending: false });

  return { data: data || [], error };
}

export async function saveOutfit(outfit) {
  const payload = {
    name: outfit.name,
    style: outfit.style || null,
    occasion: outfit.occasion || null,
    total_price: outfit.total_price || null,
    currency: outfit.currency || "KZT",
    outfit_payload: outfit.outfit_payload || {},
    source_type: outfit.source_type || "manual",
  };

  const { data, error } = await supabase
    .from("saved_outfits")
    .insert(payload)
    .select("id, name, style, occasion, total_price, currency, outfit_payload, source_type, created_at")
    .single();

  return { data, error };
}

export async function deleteSavedOutfit(id) {
  const { error } = await supabase.from("saved_outfits").delete().eq("id", id);
  return { error };
}
