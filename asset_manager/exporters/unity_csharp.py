"""
UnityCSharpExporter — Generates C# MonoBehaviour scripts and JSON map data
that build the map at runtime inside Unity.

Outputs:
  - MapData.json (complete map state as structured data)
  - MapLoader.cs (C# script that reads JSON and spawns objects)
  - MapConfig.cs (ScriptableObject definition for map configuration)
  - TerrainBuilder.cs (Builds Unity Terrain from heightmap data)
  - EntitySpawner.cs (Spawns prefabs at map positions)
"""

import os
import json
import numpy as np
from asset_manager.generators.pcg.base_agent import BaseAgent
from asset_manager.shared_state import SharedState
from typing import Any


class UnityCSharpExporter(BaseAgent):
    name = "UnityCSharpExporter"

    def _run(self, shared_state: SharedState, params: dict[str, Any]) -> dict:
        output_dir = params.get("output_dir",
                                "./output/unity_export")
        scripts_dir = os.path.join(output_dir, "Scripts")
        data_dir = os.path.join(output_dir, "Data")
        os.makedirs(scripts_dir, exist_ok=True)
        os.makedirs(data_dir, exist_ok=True)

        files_created = []

        # ── 1. Export complete map data as JSON ──
        map_data_path = os.path.join(data_dir, "MapData.json")
        self._export_map_data(shared_state, map_data_path)
        files_created.append(map_data_path)

        # ── 2. Generate MapLoader.cs ──
        loader_path = os.path.join(scripts_dir, "MapLoader.cs")
        self._write_map_loader(loader_path)
        files_created.append(loader_path)

        # ── 3. Generate MapConfig.cs (ScriptableObject) ──
        config_path = os.path.join(scripts_dir, "MapConfig.cs")
        self._write_map_config(config_path)
        files_created.append(config_path)

        # ── 4. Generate TerrainBuilder.cs ──
        terrain_path = os.path.join(scripts_dir, "TerrainBuilder.cs")
        self._write_terrain_builder(terrain_path)
        files_created.append(terrain_path)

        # ── 5. Generate EntitySpawner.cs ──
        spawner_path = os.path.join(scripts_dir, "EntitySpawner.cs")
        self._write_entity_spawner(spawner_path)
        files_created.append(spawner_path)

        # ── 6. Generate WaterController.cs ──
        water_path = os.path.join(scripts_dir, "WaterController.cs")
        self._write_water_controller(water_path)
        files_created.append(water_path)

        return {
            "files_created": files_created,
            "scripts_count": 5,
            "data_file": map_data_path,
            "output_dir": scripts_dir,
        }

    def _export_map_data(self, state: SharedState, path: str):
        """Export complete map state as JSON for runtime loading."""
        def _int(v):
            return int(v) if hasattr(v, 'item') else v

        entities = []
        for e in state.entities:
            entities.append({
                "type": e.entity_type,
                "position": {"x": _int(e.position[0]), "y": 0, "z": _int(e.position[1])},
                "size": {"x": _int(e.size[0]), "y": 5, "z": _int(e.size[1])},
                "variant": e.variant,
                "metadata": {k: (_int(v) if isinstance(v, (int, float)) else str(v))
                             for k, v in e.metadata.items()},
            })

        paths = []
        for p in state.paths:
            paths.append({
                "type": p.path_type,
                "width": _int(p.width),
                "waypoints": [{"x": _int(wp[0]), "y": 0, "z": _int(wp[1])} for wp in p.waypoints],
                "metadata": {k: str(v) for k, v in p.metadata.items()},
            })

        labels = []
        for l in state.labels:
            labels.append({
                "text": l.text,
                "position": {"x": _int(l.position[0]), "y": 5, "z": _int(l.position[1])},
                "category": l.category,
                "fontSize": l.font_size,
                "color": l.color,
            })

        map_data = {
            "config": {
                "width": state.config.width,
                "height": state.config.height,
                "biome": state.config.biome,
                "mapType": state.config.map_type,
                "seed": state.config.seed,
                "terrainMaxHeight": 100,
            },
            "mapName": state.metadata.get("map_name", "Generated Map"),
            "entities": entities,
            "paths": paths,
            "labels": labels,
            "stats": {
                "totalEntities": len(entities),
                "totalPaths": len(paths),
                "totalLabels": len(labels),
                "waterCoverage": float(state.water_mask.mean()),
                "walkableCoverage": float(state.walkability.mean()),
            },
        }

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(map_data, f, indent=2)

    def _write_map_loader(self, path: str):
        """Generate the main MapLoader MonoBehaviour."""
        code = '''using UnityEngine;
using System.Collections.Generic;
using System.IO;

/// <summary>
/// Main entry point for loading a procedurally generated map.
/// Attach to an empty GameObject in your scene.
/// Coordinates TerrainBuilder, EntitySpawner, and WaterController.
/// </summary>
public class MapLoader : MonoBehaviour
{
    [Header("Map Data")]
    [Tooltip("Path to MapData.json (relative to StreamingAssets)")]
    public string mapDataPath = "MapData.json";

    [Header("References")]
    public TerrainBuilder terrainBuilder;
    public EntitySpawner entitySpawner;
    public WaterController waterController;

    [Header("Settings")]
    public bool loadOnStart = true;
    public bool showDebugLabels = true;

    private MapData _mapData;

    void Start()
    {
        if (loadOnStart)
            LoadMap();
    }

    public void LoadMap()
    {
        string fullPath = Path.Combine(Application.streamingAssetsPath, mapDataPath);

        if (!File.Exists(fullPath))
        {
            Debug.LogError($"MapLoader: Map data not found at {fullPath}");
            return;
        }

        string json = File.ReadAllText(fullPath);
        _mapData = JsonUtility.FromJson<MapData>(json);

        Debug.Log($"MapLoader: Loaded \\"{_mapData.mapName}\\" " +
                  $"({_mapData.config.width}x{_mapData.config.height}, " +
                  $"{_mapData.entities.Length} entities)");

        // Phase 1: Build terrain
        if (terrainBuilder != null)
            terrainBuilder.BuildTerrain(_mapData.config);

        // Phase 2: Setup water
        if (waterController != null)
            waterController.SetupWater(_mapData);

        // Phase 3: Spawn entities
        if (entitySpawner != null)
            entitySpawner.SpawnEntities(_mapData.entities, _mapData.config);

        // Phase 4: Place labels (if enabled)
        if (showDebugLabels)
            PlaceDebugLabels();
    }

    private void PlaceDebugLabels()
    {
        if (_mapData.labels == null) return;

        foreach (var label in _mapData.labels)
        {
            GameObject labelObj = new GameObject($"Label_{label.text}");
            labelObj.transform.position = new Vector3(
                label.position.x, label.position.y + 10, label.position.z);
            labelObj.transform.SetParent(transform);

            // Add TextMesh for world-space labels (or use TextMeshPro)
            TextMesh textMesh = labelObj.AddComponent<TextMesh>();
            textMesh.text = label.text;
            textMesh.fontSize = label.fontSize * 4;
            textMesh.alignment = TextAlignment.Center;
            textMesh.anchor = TextAnchor.MiddleCenter;
            textMesh.characterSize = 0.5f;
        }
    }

    public MapData GetMapData() => _mapData;
}

// ── Data classes matching MapData.json structure ──

[System.Serializable]
public class MapData
{
    public MapConfigData config;
    public string mapName;
    public EntityData[] entities;
    public PathData[] paths;
    public LabelData[] labels;
    public MapStats stats;
}

[System.Serializable]
public class MapConfigData
{
    public int width;
    public int height;
    public string biome;
    public string mapType;
    public int seed;
    public float terrainMaxHeight;
}

[System.Serializable]
public class EntityData
{
    public string type;
    public Vector3Data position;
    public Vector3Data size;
    public string variant;
}

[System.Serializable]
public class PathData
{
    public string type;
    public int width;
    public Vector3Data[] waypoints;
}

[System.Serializable]
public class LabelData
{
    public string text;
    public Vector3Data position;
    public string category;
    public int fontSize;
    public string color;
}

[System.Serializable]
public class Vector3Data
{
    public float x, y, z;
    public Vector3 ToVector3() => new Vector3(x, y, z);
}

[System.Serializable]
public class MapStats
{
    public int totalEntities;
    public int totalPaths;
    public int totalLabels;
    public float waterCoverage;
    public float walkableCoverage;
}
'''
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)

    def _write_map_config(self, path: str):
        code = '''using UnityEngine;

/// <summary>
/// ScriptableObject for map generation configuration.
/// Create via Assets > Create > MapGen > MapConfig
/// </summary>
[CreateAssetMenu(fileName = "NewMapConfig", menuName = "MapGen/MapConfig")]
public class MapConfig : ScriptableObject
{
    [Header("Map Dimensions")]
    public int width = 512;
    public int height = 512;

    [Header("Biome")]
    public BiomeType biome = BiomeType.Forest;
    public MapType mapType = MapType.Village;

    [Header("Generation")]
    public int seed = 42;
    public float terrainMaxHeight = 100f;
    public float terrainScale = 1f;

    [Header("Density")]
    [Range(0f, 1f)] public float vegetationDensity = 0.7f;
    [Range(0f, 1f)] public float structureDensity = 0.5f;

    [Header("Water")]
    public bool generateWater = true;
    public int riverCount = 1;
    public int lakeCount = 0;
}

public enum BiomeType
{
    Forest, Mountain, Desert, Swamp, Plains, Tundra, Volcanic, Cave, Dungeon
}

public enum MapType
{
    Village, City, Dungeon, Cave, Arena, Wilderness, Camp, Outpost, OpenWorld
}
'''
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)

    def _write_terrain_builder(self, path: str):
        code = '''using UnityEngine;
using System.IO;

/// <summary>
/// Builds Unity Terrain from exported heightmap and splatmap data.
/// Reads RAW heightmap and applies terrain layers based on splatmap.
/// </summary>
public class TerrainBuilder : MonoBehaviour
{
    [Header("Terrain Data Paths (relative to StreamingAssets)")]
    public string heightmapPath = "Terrain/heightmap.raw";
    public string splatmapPath = "Terrain/splatmap_0.png";

    [Header("Terrain Settings")]
    public float maxHeight = 100f;
    public Material terrainMaterial;

    [Header("Terrain Layers")]
    public TerrainLayer[] terrainLayers;

    private Terrain _terrain;
    private TerrainData _terrainData;

    public void BuildTerrain(MapConfigData config)
    {
        int resolution = Mathf.Max(config.width, config.height);

        // Create or get Terrain component
        _terrain = GetComponent<Terrain>();
        if (_terrain == null)
        {
            _terrainData = new TerrainData();
            _terrain = Terrain.CreateTerrainGameObject(_terrainData)
                .GetComponent<Terrain>();
        }
        else
        {
            _terrainData = _terrain.terrainData;
        }

        // Configure terrain size
        int heightmapRes = NextPowerOfTwo(resolution) + 1;
        _terrainData.heightmapResolution = heightmapRes;
        _terrainData.size = new Vector3(config.width, config.terrainMaxHeight, config.height);

        // Load and apply heightmap
        LoadHeightmap(heightmapRes);

        // Load and apply splatmap
        if (terrainLayers != null && terrainLayers.Length > 0)
        {
            _terrainData.terrainLayers = terrainLayers;
            LoadSplatmap();
        }

        // Apply material
        if (terrainMaterial != null)
            _terrain.materialTemplate = terrainMaterial;

        Debug.Log($"TerrainBuilder: Built {config.width}x{config.height} terrain, " +
                  $"max height {config.terrainMaxHeight}");
    }

    private void LoadHeightmap(int resolution)
    {
        string fullPath = Path.Combine(Application.streamingAssetsPath, heightmapPath);

        if (!File.Exists(fullPath))
        {
            Debug.LogWarning($"TerrainBuilder: Heightmap not found at {fullPath}");
            return;
        }

        byte[] rawData = File.ReadAllBytes(fullPath);
        int pixelCount = rawData.Length / 2; // 16-bit = 2 bytes per pixel
        int dataRes = (int)Mathf.Sqrt(pixelCount);

        float[,] heights = new float[resolution, resolution];

        for (int z = 0; z < resolution; z++)
        {
            for (int x = 0; x < resolution; x++)
            {
                // Map from terrain resolution to data resolution
                int sx = Mathf.Clamp(x * dataRes / resolution, 0, dataRes - 1);
                int sz = Mathf.Clamp(z * dataRes / resolution, 0, dataRes - 1);
                int idx = (sz * dataRes + sx) * 2;

                if (idx + 1 < rawData.Length)
                {
                    ushort value = (ushort)(rawData[idx] | (rawData[idx + 1] << 8));
                    heights[z, x] = value / 65535f;
                }
            }
        }

        _terrainData.SetHeights(0, 0, heights);
    }

    private void LoadSplatmap()
    {
        string fullPath = Path.Combine(Application.streamingAssetsPath, splatmapPath);

        if (!File.Exists(fullPath))
        {
            Debug.LogWarning($"TerrainBuilder: Splatmap not found at {fullPath}");
            return;
        }

        byte[] pngData = File.ReadAllBytes(fullPath);
        Texture2D splatTex = new Texture2D(2, 2);
        splatTex.LoadImage(pngData);

        int alphamapRes = _terrainData.alphamapResolution;
        int layerCount = Mathf.Min(terrainLayers.Length, 4);

        float[,,] alphamaps = new float[alphamapRes, alphamapRes, layerCount];

        for (int z = 0; z < alphamapRes; z++)
        {
            for (int x = 0; x < alphamapRes; x++)
            {
                float u = (float)x / alphamapRes;
                float v = (float)z / alphamapRes;
                Color pixel = splatTex.GetPixelBilinear(u, v);

                float[] channels = { pixel.r, pixel.g, pixel.b, pixel.a };
                float sum = 0;
                for (int i = 0; i < layerCount; i++) sum += channels[i];
                if (sum > 0)
                    for (int i = 0; i < layerCount; i++)
                        alphamaps[z, x, i] = channels[i] / sum;
            }
        }

        _terrainData.SetAlphamaps(0, 0, alphamaps);
        Destroy(splatTex);
    }

    private int NextPowerOfTwo(int n)
    {
        int v = 1;
        while (v < n) v <<= 1;
        return v;
    }
}
'''
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)

    def _write_entity_spawner(self, path: str):
        code = '''using UnityEngine;
using System.Collections.Generic;

/// <summary>
/// Spawns map entities (buildings, trees, props) from MapData.
/// Uses a prefab lookup dictionary to map entity types/variants to Unity prefabs.
/// </summary>
public class EntitySpawner : MonoBehaviour
{
    [Header("Prefab Mappings")]
    [Tooltip("Drag prefabs here. Name them to match entity variants.")]
    public PrefabMapping[] prefabMappings;

    [Header("Settings")]
    public bool alignToTerrain = true;
    public bool randomRotation = true;
    public float yOffset = 0f;

    [Header("LOD")]
    public float maxSpawnDistance = 500f;
    public bool usePooling = true;

    private Dictionary<string, GameObject> _prefabLookup;
    private Terrain _terrain;
    private Transform _entityParent;

    public void SpawnEntities(EntityData[] entities, MapConfigData config)
    {
        BuildPrefabLookup();
        _terrain = Terrain.activeTerrain;

        // Create parent container
        _entityParent = new GameObject("MapEntities").transform;
        _entityParent.SetParent(transform);

        int spawned = 0;
        int skipped = 0;

        foreach (var entity in entities)
        {
            GameObject prefab = ResolvePrefab(entity.type, entity.variant);

            if (prefab == null)
            {
                skipped++;
                continue;
            }

            Vector3 position = entity.position.ToVector3();

            // Snap to terrain height
            if (alignToTerrain && _terrain != null)
            {
                position.y = _terrain.SampleHeight(position) + yOffset;
            }

            // Spawn
            GameObject instance = Instantiate(prefab, position,
                GetRotation(entity), _entityParent);
            instance.name = $"{entity.type}_{spawned}";

            // Scale based on entity size
            if (entity.size.x > 0 && entity.size.z > 0)
            {
                instance.transform.localScale = entity.size.ToVector3();
            }

            spawned++;
        }

        Debug.Log($"EntitySpawner: Spawned {spawned} entities, skipped {skipped} " +
                  $"(no prefab match)");
    }

    private void BuildPrefabLookup()
    {
        _prefabLookup = new Dictionary<string, GameObject>();

        if (prefabMappings == null) return;

        foreach (var mapping in prefabMappings)
        {
            if (mapping.prefab != null)
            {
                _prefabLookup[mapping.entityKey.ToLower()] = mapping.prefab;
            }
        }
    }

    private GameObject ResolvePrefab(string entityType, string variant)
    {
        // Try specific variant first, then generic type
        string variantKey = $"{entityType}_{variant}".ToLower();
        if (_prefabLookup.TryGetValue(variantKey, out var prefab))
            return prefab;

        if (_prefabLookup.TryGetValue(entityType.ToLower(), out prefab))
            return prefab;

        return null;
    }

    private Quaternion GetRotation(EntityData entity)
    {
        if (randomRotation && entity.type != "building" && entity.type != "room")
        {
            return Quaternion.Euler(0, Random.Range(0f, 360f), 0);
        }
        return Quaternion.identity;
    }
}

[System.Serializable]
public class PrefabMapping
{
    [Tooltip("Key to match: entityType or entityType_variant (case insensitive)")]
    public string entityKey;
    public GameObject prefab;
}
'''
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)

    def _write_water_controller(self, path: str):
        code = '''using UnityEngine;
using System.IO;

/// <summary>
/// Sets up water planes and river splines from map data.
/// Supports both simple plane-based water and shader-based water systems.
/// </summary>
public class WaterController : MonoBehaviour
{
    [Header("Water Settings")]
    public Material waterMaterial;
    public float waterLevel = 5f;
    public bool useWaterMask = true;

    [Header("Water Mask")]
    public string waterMaskPath = "Terrain/water_mask.png";

    [Header("River Settings")]
    public float riverMeshWidth = 3f;
    public Material riverMaterial;

    public void SetupWater(MapData mapData)
    {
        float width = mapData.config.width;
        float height = mapData.config.height;

        // Create main water plane
        if (mapData.stats.waterCoverage > 0.001f)
        {
            CreateWaterPlane(width, height);
        }

        // Create river meshes from path data
        if (mapData.paths != null)
        {
            foreach (var path in mapData.paths)
            {
                if (path.type == "river" && path.waypoints != null)
                {
                    CreateRiverMesh(path);
                }
            }
        }

        Debug.Log($"WaterController: Water coverage {mapData.stats.waterCoverage:P1}");
    }

    private void CreateWaterPlane(float width, float height)
    {
        GameObject waterObj = GameObject.CreatePrimitive(PrimitiveType.Plane);
        waterObj.name = "WaterSurface";
        waterObj.transform.SetParent(transform);
        waterObj.transform.position = new Vector3(width / 2f, waterLevel, height / 2f);
        waterObj.transform.localScale = new Vector3(width / 10f, 1f, height / 10f);

        if (waterMaterial != null)
        {
            waterObj.GetComponent<Renderer>().material = waterMaterial;
        }

        // Disable collider by default (configure in your project)
        var col = waterObj.GetComponent<Collider>();
        if (col != null) col.enabled = false;
    }

    private void CreateRiverMesh(PathData riverPath)
    {
        if (riverPath.waypoints.Length < 2) return;

        GameObject riverObj = new GameObject($"River_{riverPath.waypoints.Length}pts");
        riverObj.transform.SetParent(transform);

        // Create a line renderer for visualization
        LineRenderer lr = riverObj.AddComponent<LineRenderer>();
        lr.positionCount = riverPath.waypoints.Length;
        lr.startWidth = riverMeshWidth;
        lr.endWidth = riverMeshWidth;

        Terrain terrain = Terrain.activeTerrain;

        for (int i = 0; i < riverPath.waypoints.Length; i++)
        {
            Vector3 pos = riverPath.waypoints[i].ToVector3();
            if (terrain != null)
                pos.y = terrain.SampleHeight(pos) - 0.5f;
            else
                pos.y = waterLevel - 0.5f;
            lr.SetPosition(i, pos);
        }

        if (riverMaterial != null)
            lr.material = riverMaterial;
    }
}
'''
        with open(path, 'w', encoding='utf-8') as f:
            f.write(code)
