using System;
using System.Collections.Generic;
using UnityEngine;

namespace InkDrift
{
    /// <summary>Baked instance data for the GPU-instanced foliage renderer (per layer, bucketed into spatial cells).</summary>
    [CreateAssetMenu(menuName = "InkDrift/Foliage Data")]
    public class FoliageData : ScriptableObject
    {
        [Serializable]
        public class Layer
        {
            public string name;
            public Mesh mesh;
            public Mesh lodMesh;
            public Material[] materials;
            public Material[] lodMaterials;
            public Matrix4x4 meshOffset = Matrix4x4.identity;
            public Matrix4x4 lodOffset = Matrix4x4.identity;
            public float lodDistance = 110f;
            public float cullDistance = 900f;
            public bool castShadows = true;
            public Matrix4x4[] instances = Array.Empty<Matrix4x4>();
            public int[] cellStart = Array.Empty<int>();
            public int[] cellCount = Array.Empty<int>();
            public Bounds[] cellBounds = Array.Empty<Bounds>();
        }

        public List<Layer> layers = new List<Layer>();
        public float cellSize = 96f;
    }
}
