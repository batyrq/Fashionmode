import { getSession, supabase } from "./auth.js";

export const FAVORITE_SOURCE_TYPE = "favorite_product";

function dedupeFavoriteRecords(records) {
  const uniqueByKey = new Map();

  for (const record of records) {
    const favoriteKey = record.favorite_key ? String(record.favorite_key) : null;
    const dedupeKey = favoriteKey || `record:${record.id}`;
    if (!uniqueByKey.has(dedupeKey)) {
      uniqueByKey.set(dedupeKey, record);
    }
  }

  return Array.from(uniqueByKey.values());
}

function buildFavoritePayload(product) {
  const favoriteKey = product.favorite_key || product.catalog_display_id || product.id;
  return {
    favorite_key: favoriteKey,
    catalog_display_id: product.catalog_display_id || product.id,
    favorite_product_uuid: product.favorite_product_uuid || null,
    product_snapshot: {
      id: product.id,
      catalog_display_id: product.catalog_display_id || product.id,
      favorite_key: favoriteKey,
      favorite_product_uuid: product.favorite_product_uuid || null,
      name: product.name,
      price: product.price || 0,
      currency: product.currency || "KZT",
      category: product.category || null,
      outfit_category: product.outfit_category || null,
      colors: product.colors || [],
      sizes: product.sizes || [],
      image_url: product.image_url || "",
      source_url: product.source_url || product.url || null,
    },
  };
}

function normalizeFavoriteRecord(record) {
  const payload = record.outfit_payload || {};
  const snapshot = payload.product_snapshot || {};
  return {
    id: record.id,
    favorite_key: payload.favorite_key || snapshot.favorite_key || record.name,
    catalog_display_id: payload.catalog_display_id || snapshot.catalog_display_id || snapshot.id,
    favorite_product_uuid: payload.favorite_product_uuid || snapshot.favorite_product_uuid || null,
    created_at: record.created_at,
    product: {
      ...snapshot,
      favorite_key: payload.favorite_key || snapshot.favorite_key || record.name,
      catalog_display_id: payload.catalog_display_id || snapshot.catalog_display_id || snapshot.id,
      favorite_product_uuid: payload.favorite_product_uuid || snapshot.favorite_product_uuid || null,
    },
  };
}

export async function listFavoriteProducts() {
  const { data, error } = await supabase
    .from("saved_outfits")
    .select("id, name, total_price, currency, outfit_payload, source_type, created_at")
    .eq("source_type", FAVORITE_SOURCE_TYPE)
    .order("created_at", { ascending: false });

  const normalized = (data || []).map(normalizeFavoriteRecord);
  return {
    data: dedupeFavoriteRecords(normalized),
    error,
  };
}

export async function getFavoriteMap() {
  const { data, error } = await listFavoriteProducts();
  if (error) {
    return { data: null, error };
  }

  const byKey = new Map();
  for (const record of data) {
    if (record.favorite_key) {
      byKey.set(String(record.favorite_key), record);
    }
  }

  return { data: byKey, error: null };
}

export async function addFavoriteProduct(product) {
  const { data: session } = await getSession();
  if (!session) {
    return {
      data: null,
      error: { message: "AUTH_REQUIRED" },
    };
  }

  const favoritePayload = buildFavoritePayload(product);
  const { data: existingMap, error: existingError } = await getFavoriteMap();
  if (existingError) {
    return { data: null, error: existingError };
  }

  const existingRecord = existingMap?.get(String(favoritePayload.favorite_key));
  if (existingRecord) {
    return { data: existingRecord, error: null };
  }

  const insertPayload = {
    name: product.name || `Favorite ${favoritePayload.favorite_key}`,
    style: "favorite",
    occasion: null,
    total_price: product.price || null,
    currency: product.currency || "KZT",
    source_type: FAVORITE_SOURCE_TYPE,
    outfit_payload: favoritePayload,
  };

  const { data, error } = await supabase
    .from("saved_outfits")
    .insert(insertPayload)
    .select("id, name, total_price, currency, outfit_payload, source_type, created_at")
    .single();

  return {
    data: data ? normalizeFavoriteRecord(data) : null,
    error,
  };
}

export async function removeFavoriteProductByRecordId(recordId) {
  const { error } = await supabase.from("saved_outfits").delete().eq("id", recordId);
  return { error };
}

export async function removeFavoriteProductByKey(favoriteKey) {
  const { data: favoriteRecords, error: existingError } = await listFavoriteProducts();
  if (existingError) {
    return { error: existingError };
  }

  const matchingRecords = (favoriteRecords || []).filter(
    (record) => String(record.favorite_key) === String(favoriteKey),
  );
  if (!matchingRecords.length) {
    return { error: null };
  }

  const deleteResults = await Promise.all(
    matchingRecords.map((record) => removeFavoriteProductByRecordId(record.id)),
  );
  const failedResult = deleteResults.find((result) => result.error);
  return { error: failedResult?.error || null };
}

export async function toggleFavoriteProduct(product) {
  const favoriteKey = product.favorite_key || product.catalog_display_id || product.id;
  const { data: favoriteMap, error: existingError } = await getFavoriteMap();
  if (existingError) {
    return { data: null, error: existingError, isFavorite: false };
  }

  const existingRecord = favoriteMap?.get(String(favoriteKey));
  if (existingRecord) {
    const { error } = await removeFavoriteProductByRecordId(existingRecord.id);
    return { data: null, error, isFavorite: false };
  }

  const { data, error } = await addFavoriteProduct(product);
  return { data, error, isFavorite: !error };
}
