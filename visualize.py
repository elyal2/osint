from flask import Flask, render_template, jsonify, request
from graph_database import EntityGraph
from config import AppConfig
import os
import logging

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Create templates directory and HTML file if not exists
os.makedirs('templates', exist_ok=True)
with open('templates/index.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Entity Relationship Graph</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.2/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
    <style>
        body, html { width: 100%; height: 100%; margin: 0; padding: 0; overflow: hidden; }
        #main-container { height: 100vh; display: flex; }
        #sidebar { 
            width: 350px; 
            background: #f8f9fa; 
            border-right: 1px solid #ddd; 
            overflow-y: auto; 
            flex-shrink: 0;
            z-index: 100;
        }
        #graph-area { 
            flex: 1; 
            position: relative; 
            overflow: hidden;
        }
        #graph-container { 
            width: 100%; 
            height: 100%; 
            cursor: grab; 
        }
        #graph-container:active { cursor: grabbing; }
        
        /* Toolbar fijo en la parte superior del grafo */
        #graph-toolbar {
            position: absolute;
            top: 10px;
            left: 10px;
            right: 10px;
            background: rgba(255,255,255,0.95);
            backdrop-filter: blur(10px);
            border-radius: 8px;
            padding: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            z-index: 50;
            display: flex;
            gap: 10px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .filter-group {
            display: flex;
            gap: 5px;
            align-items: center;
            background: #fff;
            padding: 5px 10px;
            border-radius: 20px;
            border: 1px solid #ddd;
            font-size: 12px;
        }
        
        .filter-toggle {
            background: none;
            border: none;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 11px;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        .filter-toggle.active {
            background: #007bff;
            color: white;
        }
        
        .filter-toggle.inactive {
            background: #e9ecef;
            color: #6c757d;
        }
        
        .highlighted { stroke: #e17055 !important; stroke-width: 4px !important; }
        .dimmed { opacity: 0.2; }
        .hidden-node { opacity: 0.1; }
        .hidden-link { opacity: 0.05; }
        
        .autocomplete-items { 
            position: absolute; 
            border: 1px solid #d4d4d4; 
            border-bottom: none; 
            border-top: none; 
            z-index: 99; 
            top: 100%; 
            left: 0; 
            right: 0; 
            background: #fff; 
            max-height: 200px; 
            overflow-y: auto; 
        }
        .autocomplete-items div { 
            padding: 10px; 
            cursor: pointer; 
            background-color: #fff; 
            border-bottom: 1px solid #d4d4d4; 
        }
        .autocomplete-items div:hover { background-color: #e9e9e9; }
        
        .qa-response { 
            margin-top: 10px; 
            background: #eef; 
            padding: 10px; 
            border-radius: 5px; 
        }
        
        .node { cursor: pointer; }
        .node circle { stroke: #fff; stroke-width: 1.5px; }
        .link { stroke-opacity: 0.6; stroke-width: 1px; fill: none; }
        .node-label { font-size: 12px; pointer-events: none; }
        .link-label { font-size: 10px; pointer-events: none; fill: #666; }
        .toast { background: rgba(0,0,0,0.8); color: white; }
        
        .sidebar-section {
            border-bottom: 1px solid #dee2e6;
            padding: 15px;
        }
        .sidebar-section h6 {
            margin-bottom: 10px;
            color: #495057;
            font-weight: 600;
        }
        
        .stats-bar {
            background: rgba(0,123,255,0.1);
            color: #0056b3;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 12px;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
<div id="main-container">
  <!-- Sidebar -->
  <div id="sidebar">
    
    <!-- Estadísticas -->
    <div class="sidebar-section">
      <div id="stats-bar" class="stats-bar">
        Cargando datos...
      </div>
    </div>
    
    <!-- Navegación -->
    <div class="sidebar-section">
      <h6>🔍 Navegación</h6>
      <div class="mb-2">
        <input type="text" id="entity-search" class="form-control form-control-sm mb-1" placeholder="Buscar entidad...">
        <button id="search-btn" class="btn btn-primary btn-sm w-100 mb-2">Buscar y centrar</button>
      </div>
      <div class="mb-2">
        <input type="text" id="path-from" class="form-control form-control-sm mb-1" placeholder="Entidad origen...">
        <input type="text" id="path-to" class="form-control form-control-sm mb-1" placeholder="Entidad destino...">
        <button id="path-btn" class="btn btn-secondary btn-sm w-100 mb-2">Resaltar camino</button>
      </div>
      <div class="mb-2">
        <div class="d-flex gap-1 mb-1">
          <input type="text" id="subgraph-entity" class="form-control form-control-sm" placeholder="Entidad para subgrafo...">
          <input type="number" id="subgraph-depth" min="1" max="5" value="3" class="form-control form-control-sm" style="width:60px;">
        </div>
        <div class="d-flex gap-1">
          <button id="subgraph-btn" class="btn btn-info btn-sm flex-fill">Subgrafo</button>
          <button id="reset-btn" class="btn btn-outline-secondary btn-sm flex-fill">Reset</button>
        </div>
      </div>
    </div>
    
    <!-- Pregunta al LLM -->
    <div class="sidebar-section">
      <h6>🤖 Pregunta al LLM</h6>
      <div class="qa-box" id="qa-box" style="display:none;">
        <textarea id="qa-question" class="form-control form-control-sm mb-2" placeholder="Escribe tu pregunta..." rows="3"></textarea>
        <button id="qa-submit" class="btn btn-success btn-sm w-100">Preguntar</button>
        <div class="qa-response" id="qa-response" style="display:none;"></div>
      </div>
      <div id="llm-hint" class="text-muted small">Selecciona una entidad en el grafo para habilitar la pregunta.</div>
    </div>
    
    <!-- Leyenda -->
    <div class="sidebar-section">
      <h6>📊 Leyenda</h6>
      <div id="legend-section">
        <!-- Leyenda de colores y categorías -->
      </div>
    </div>
    
  </div>
  
  <!-- Área del grafo -->
  <div id="graph-area">
    <!-- Toolbar de filtros flotante -->
    <div id="graph-toolbar">
      <div class="filter-group">
        <span><strong>Entidades:</strong></span>
        <div id="entity-filters"></div>
      </div>
      <div class="filter-group">
        <span><strong>Relaciones:</strong></span>
        <div id="relation-filters"></div>
      </div>
      <div class="filter-group">
        <span><strong>Categorías:</strong></span>
        <div id="category-filters"></div>
      </div>
    </div>
    
    <!-- Contenedor del grafo -->
    <div id="graph-container"></div>
  </div>
  
</div>
<script>
// Variables globales para el grafo
let svg, simulation, nodes, links;
let width, height;
let allEntities = [];
let originalData = { nodes: [], links: [] }; // Datos originales sin filtrar
let currentFilters = {
    entities: new Set(['Person', 'Organization', 'Location', 'Date', 'Event', 'Object', 'Code']),
    relations: new Set(['explicit', 'inferred']),
    categories: new Set()
};

// Colores para categorías de relación
const categoryColors = {
    affiliation: '#8e44ad',
    mobility: '#2980b9',
    interaction: '#16a085',
    influence: '#e67e22',
    event_participation: '#c0392b',
    transaction: '#f1c40f',
    authorship: '#2d3436',
    location: '#00b894',
    temporal: '#636e72',
    succession: '#fdcb6e',
    vulnerability: '#d35400'
};

// Función para inicializar el grafo
function initGraph() {
    const container = document.getElementById('graph-container');
    width = container.clientWidth;
    height = container.clientHeight;
    
    // Crear SVG con zoom
    svg = d3.select('#graph-container')
        .append('svg')
        .attr('width', width)
        .attr('height', height);
    
    // Crear grupo para el contenido del grafo
    const g = svg.append('g');
    
    // Configurar zoom
    const zoom = d3.zoom()
        .scaleExtent([0.1, 4])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        });
    
    svg.call(zoom);
    
    // Crear simulación con mejores parámetros
    simulation = d3.forceSimulation()
        .force('link', d3.forceLink().id(d => d.id).distance(120).strength(0.5))
        .force('charge', d3.forceManyBody().strength(-400).distanceMax(300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30))
        .alphaDecay(0.02)
        .velocityDecay(0.3);
    
    // Cargar datos iniciales
    loadGraph('/api/graph');
    
    // Cargar entidades para autocomplete
    fetch('/api/entities')
        .then(r => r.json())
        .then(data => {
            allEntities = data.entities || [];
            initAutocomplete();
        });
}

// Función para cargar el grafo
function loadGraph(url = '/api/graph') {
    // Mostrar indicador de carga
    const loadingDiv = document.createElement('div');
    loadingDiv.className = 'position-absolute top-50 start-50 translate-middle';
    loadingDiv.innerHTML = '<div class="spinner-border text-primary" role="status"><span class="visually-hidden">Cargando...</span></div>';
    document.getElementById('graph-container').appendChild(loadingDiv);
    
    fetch(url)
    .then(response => response.json())
    .then(data => {
        // Remover indicador de carga
        const loadingElement = document.querySelector('.spinner-border');
        if (loadingElement) {
            loadingElement.parentElement.remove();
        }
        
        // Verificar si hay mensaje de error o información
        if (data.message && !data.nodes) {
            const messageDiv = document.createElement('div');
            messageDiv.className = 'position-absolute top-50 start-50 translate-middle text-center';
            messageDiv.style.maxWidth = '600px';
            messageDiv.innerHTML = `
                <h3>${data.message}</h3>
                ${data.message.includes('vacía') ? `
                    <p><strong>Para empezar:</strong></p>
                    <ul class="text-start d-inline-block">
                        <li>Analiza un archivo de texto: <code>python main.py --file documento.txt --store-db</code></li>
                        <li>Analiza una página web: <code>python main.py --url https://ejemplo.com --store-db</code></li>
                        <li>Analiza un PDF: <code>python main.py --pdf documento.pdf --store-db</code></li>
                    </ul>
                ` : ''}
            `;
            document.getElementById('graph-container').appendChild(messageDiv);
            return;
        }
        
        if (data.error) {
            console.error('Error:', data.error);
            const errorDiv = document.createElement('div');
            errorDiv.className = 'position-absolute top-50 start-50 translate-middle text-danger';
            errorDiv.innerHTML = `
                <h3>Error</h3>
                <p>${data.message || data.error}</p>
            `;
            document.getElementById('graph-container').appendChild(errorDiv);
            return;
        }
        
        // Limpiar SVG existente (mantener el grupo principal)
        svg.select('g').selectAll("*").remove();
        
        if (!data.nodes || data.nodes.length === 0) {
            const noDataDiv = document.createElement('div');
            noDataDiv.className = 'position-absolute top-50 start-50 translate-middle text-center';
            noDataDiv.innerHTML = `
                <h3>No hay datos para mostrar</h3>
                <p>Analiza un documento primero usando: python main.py --file/--url/--pdf <archivo> --store-db</p>
            `;
            document.getElementById('graph-container').appendChild(noDataDiv);
            return;
        }
        
        // Obtener el grupo principal
        const g = svg.select('g');
        
        // Crear enlaces
        links = g.append('g')
            .selectAll('line')
            .data(data.links || [])
            .enter().append('line')
            .attr('class', 'link')
            .style('stroke', d => categoryColors[d.category] || '#999')
            .attr('data-bs-toggle', 'tooltip')
            .attr('title', d => `${d.source_name || d.source} ${d.action} ${d.target_name || d.target} (${d.category || 'sin categoría'})`);
    
        // Crear nodos
        nodes = g.append('g')
            .selectAll('g')
            .data(data.nodes)
            .enter().append('g')
            .attr('class', 'node')
            .attr('data-bs-toggle', 'tooltip')
            .attr('title', d => `${d.name} (${d.type})`)
            .call(d3.drag()
                .on('start', dragstarted)
                .on('drag', dragged)
                .on('end', dragended));
        
        // Añadir círculos a los nodos
        nodes.append('circle')
            .attr('r', 8)
            .style('fill', d => {
                switch(d.type) {
                    case 'Person': return '#ff6b6b';
                    case 'Organization': return '#4ecdc4';
                    case 'Location': return '#45b7d1';
                    case 'Date': return '#96ceb4';
                    case 'Event': return '#ff9ff3';
                    case 'Object': return '#feca57';
                    case 'Code': return '#54a0ff';
                    default: return '#feca57';
                }
            });
        
        // Añadir etiquetas a los nodos
        nodes.append('text')
            .attr('class', 'node-label')
            .attr('dx', 12)
            .attr('dy', '.35em')
            .text(d => d.name);
        
        // Añadir etiquetas a los enlaces
        if (data.links && data.links.length > 0) {
            g.append('g')
                .selectAll('text')
                .data(data.links)
                .enter().append('text')
                .attr('class', 'link-label')
                .text(d => d.action)
                .attr('text-anchor', 'middle');
        }
        
        // Actualizar simulación
        simulation
            .nodes(data.nodes)
            .on('tick', ticked);
        
        simulation.force('link')
            .links(data.links || []);
        
        // Ajustar fuerzas dinámicamente
        const nodeCount = data.nodes.length;
        const chargeStrength = Math.max(-800, -200 - nodeCount * 3);
        simulation.force('charge').strength(chargeStrength);
        
        // Inicializar tooltips Bootstrap
        initBootstrapTooltips();
        
        // Crear leyenda
        createLegend();
        
        // Crear filtros
        createFilters();
        
        // Añadir eventos de click a nodos
        addNodeClickEvents();
        
        // Guardar datos originales (solo aquí)
        originalData = {
            nodes: [...data.nodes],
            links: [...data.links]
        };
        // Inicializar filtros y estadísticas con los datos actuales
        createFilters();
        updateStatsBar();
        
        console.log('Grafo cargado:', data.nodes.length, 'nodos,', (data.links || []).length, 'enlaces');
        
    }).catch(error => {
        console.error('Error loading graph:', error);
        const loadingElement = document.querySelector('.spinner-border');
        if (loadingElement) {
            loadingElement.parentElement.remove();
        }
        const errorDiv = document.createElement('div');
        errorDiv.className = 'position-absolute top-50 start-50 translate-middle text-danger';
        errorDiv.innerHTML = `
            <h3>Error de conexión</h3>
            <p>No se pudo cargar el grafo. Verifica que el servidor esté funcionando.</p>
        `;
        document.getElementById('graph-container').appendChild(errorDiv);
    });
}

// Inicializar tooltips Bootstrap
function initBootstrapTooltips() {
    // Destruir tooltips existentes
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
}

// Función para crear leyenda
function createLegend() {
    const legendSection = document.getElementById('legend-section');
    legendSection.innerHTML = '';
    
    // Leyenda de tipos de entidad
    const entityLegend = document.createElement('div');
    entityLegend.className = 'mb-3';
    entityLegend.innerHTML = '<h6>Tipos de Entidad:</h6>';
    
    const entityTypes = [
        {type: 'Person', color: '#ff6b6b'},
        {type: 'Organization', color: '#4ecdc4'},
        {type: 'Location', color: '#45b7d1'},
        {type: 'Date', color: '#96ceb4'},
        {type: 'Event', color: '#ff9ff3'},
        {type: 'Object', color: '#feca57'},
        {type: 'Code', color: '#54a0ff'}
    ];
    
    entityTypes.forEach(item => {
        const legendItem = document.createElement('div');
        legendItem.className = 'd-flex align-items-center mb-1';
        legendItem.innerHTML = `
            <div class="me-2" style="width: 12px; height: 12px; border-radius: 50%; background-color: ${item.color};"></div>
            <small>${item.type}</small>
        `;
        entityLegend.appendChild(legendItem);
    });
    
    legendSection.appendChild(entityLegend);
    
    // Leyenda de categorías de relación
    const categoryLegend = document.createElement('div');
    categoryLegend.innerHTML = '<h6>Categorías de Relación:</h6>';
    
    Object.entries(categoryColors).forEach(([cat, color]) => {
        const legendItem = document.createElement('div');
        legendItem.className = 'd-flex align-items-center mb-1';
        legendItem.innerHTML = `
            <div class="me-2" style="width: 12px; height: 12px; border-radius: 2px; background-color: ${color};"></div>
            <small>${cat}</small>
        `;
        categoryLegend.appendChild(legendItem);
    });
    
    legendSection.appendChild(categoryLegend);
}

// Función para crear filtros modernos en el toolbar
function createFilters() {
    createEntityFilters();
    createRelationFilters();
    createCategoryFilters();
    updateStatsBar();
}

function createEntityFilters() {
    const container = document.getElementById('entity-filters');
    container.innerHTML = '';
    
    const entityTypes = ['Person', 'Organization', 'Location', 'Date', 'Event', 'Object', 'Code'];
    entityTypes.forEach(type => {
        const button = document.createElement('button');
        button.className = `filter-toggle ${currentFilters.entities.has(type) ? 'active' : 'inactive'}`;
        button.textContent = type;
        button.onclick = () => toggleEntityFilter(type);
        container.appendChild(button);
    });
}

function createRelationFilters() {
    const container = document.getElementById('relation-filters');
    container.innerHTML = '';
    
    const relationTypes = [
        {value: 'explicit', label: 'Explícitas'},
        {value: 'inferred', label: 'Inferidas'}
    ];
    
    relationTypes.forEach(rel => {
        const button = document.createElement('button');
        button.className = `filter-toggle ${currentFilters.relations.has(rel.value) ? 'active' : 'inactive'}`;
        button.textContent = rel.label;
        button.onclick = () => toggleRelationFilter(rel.value);
        container.appendChild(button);
    });
}

function createCategoryFilters() {
    const container = document.getElementById('category-filters');
    container.innerHTML = '';
    
    // Obtener categorías únicas de los datos
    const categories = new Set();
    originalData.links.forEach(link => {
        if (link.category && link.category !== 'unknown') {
            categories.add(link.category);
        }
    });
    
    // Inicializar filtros de categoría si no están establecidos
    if (currentFilters.categories.size === 0) {
        currentFilters.categories = new Set(categories);
    }
    
    categories.forEach(cat => {
        const button = document.createElement('button');
        button.className = `filter-toggle ${currentFilters.categories.has(cat) ? 'active' : 'inactive'}`;
        button.textContent = cat;
        button.style.background = currentFilters.categories.has(cat) ? categoryColors[cat] || '#007bff' : '#e9ecef';
        button.onclick = () => toggleCategoryFilter(cat);
        container.appendChild(button);
    });
}

function toggleEntityFilter(type) {
    if (currentFilters.entities.has(type)) {
        currentFilters.entities.delete(type);
    } else {
        currentFilters.entities.add(type);
    }
    applyFiltersToGraph();
    createEntityFilters(); // Actualizar botones
}

function toggleRelationFilter(type) {
    if (currentFilters.relations.has(type)) {
        currentFilters.relations.delete(type);
    } else {
        currentFilters.relations.add(type);
    }
    applyFiltersToGraph();
    createRelationFilters(); // Actualizar botones
}

function toggleCategoryFilter(cat) {
    if (currentFilters.categories.has(cat)) {
        currentFilters.categories.delete(cat);
    } else {
        currentFilters.categories.add(cat);
    }
    applyFiltersToGraph();
    createCategoryFilters(); // Actualizar botones
}

// Aplicar filtros directamente al grafo sin recargar datos
function applyFiltersToGraph() {
    if (!originalData.nodes.length) return;
    // Filtrar nodos
    const filteredNodes = originalData.nodes.filter(node => 
        currentFilters.entities.has(node.type)
    );
    const nodeIds = new Set(filteredNodes.map(n => n.id));
    // Filtrar enlaces SIEMPRE desde originalData.links
    const filteredLinks = originalData.links.filter(link => {
        const sourceId = typeof link.source === 'object' ? link.source.id : link.source;
        const targetId = typeof link.target === 'object' ? link.target.id : link.target;
        return nodeIds.has(sourceId) && 
               nodeIds.has(targetId) &&
               currentFilters.relations.has(link.source_type || 'explicit') &&
               currentFilters.categories.has(link.category || 'unknown');
    });
    // Reconstruir el grafo solo con los elementos filtrados
    updateGraphData({ nodes: filteredNodes, links: filteredLinks });
}

// Función para actualizar la barra de estadísticas
function updateStatsBar(visibleNodes = null, visibleLinks = null) {
    const statsBar = document.getElementById('stats-bar');
    const totalNodes = originalData.nodes.length;
    const totalLinks = originalData.links.length;
    
    if (visibleNodes === null) visibleNodes = totalNodes;
    if (visibleLinks === null) visibleLinks = totalLinks;
    
    if (totalNodes === 0) {
        statsBar.innerHTML = 'No hay datos cargados';
        return;
    }
    
    const nodePercentage = Math.round((visibleNodes / totalNodes) * 100);
    const linkPercentage = Math.round((visibleLinks / totalLinks) * 100);
    
    statsBar.innerHTML = `
        📊 <strong>${visibleNodes}</strong>/${totalNodes} entidades (${nodePercentage}%) • 
        🔗 <strong>${visibleLinks}</strong>/${totalLinks} relaciones (${linkPercentage}%)
    `;
}

// Función para actualizar los datos del grafo manteniendo posiciones
function updateGraphData(data) {
    if (!data.nodes || data.nodes.length === 0) {
        showNotification('No se encontraron datos para mostrar.');
        return;
    }
    
    // NO actualizar originalData aquí
    // Limpiar SVG existente (mantener el grupo principal)
    svg.select('g').selectAll("*").remove();
    
    // Obtener el grupo principal
    const g = svg.select('g');

    // Crear enlaces
    links = g.append('g')
        .selectAll('line')
        .data(data.links || [])
        .enter().append('line')
        .attr('class', 'link')
        .style('stroke', d => categoryColors[d.category] || '#999')
        .attr('data-bs-toggle', 'tooltip')
        .attr('title', d => `${d.source_name || d.source} ${d.action} ${d.target_name || d.target} (${d.category || 'sin categoría'})`);

    // Crear nodos
    nodes = g.append('g')
        .selectAll('g')
        .data(data.nodes)
        .enter().append('g')
        .attr('class', 'node')
        .attr('data-bs-toggle', 'tooltip')
        .attr('title', d => `${d.name} (${d.type})`)
        .call(d3.drag()
            .on('start', dragstarted)
            .on('drag', dragged)
            .on('end', dragended));
    
    // Añadir círculos a los nodos
    nodes.append('circle')
        .attr('r', 8)
        .style('fill', d => {
            switch(d.type) {
                case 'Person': return '#ff6b6b';
                case 'Organization': return '#4ecdc4';
                case 'Location': return '#45b7d1';
                case 'Date': return '#96ceb4';
                case 'Event': return '#ff9ff3';
                case 'Object': return '#feca57';
                case 'Code': return '#54a0ff';
                default: return '#feca57';
            }
        });
    
    // Añadir etiquetas a los nodos
    nodes.append('text')
        .attr('class', 'node-label')
        .attr('dx', 12)
        .attr('dy', '.35em')
        .text(d => d.name);
    
    // Añadir etiquetas a los enlaces
    if (data.links && data.links.length > 0) {
        g.append('g')
            .selectAll('text')
            .data(data.links)
            .enter().append('text')
            .attr('class', 'link-label')
            .text(d => d.action)
            .attr('text-anchor', 'middle');
    }
    
    // Actualizar simulación con posiciones mejoradas
    simulation
        .nodes(data.nodes)
        .on('tick', ticked);
    
    simulation.force('link')
        .links(data.links || []);
    
    // Actualizar fuerzas para el nuevo conjunto de datos
    const nodeCount = data.nodes.length;
    const linkCount = (data.links || []).length;
    
    // Ajustar fuerzas según el tamaño del grafo
    const chargeStrength = Math.max(-800, -200 - nodeCount * 5);
    const linkDistance = Math.max(80, Math.min(200, 100 + linkCount * 2));
    
    simulation.force('charge').strength(chargeStrength);
    simulation.force('link').distance(linkDistance);
    
    // Reiniciar simulación con alpha más alto para mejor distribución
    simulation.alpha(0.7).restart();
    
    // Inicializar tooltips Bootstrap
    initBootstrapTooltips();
    
    // Añadir eventos de click a nodos
    addNodeClickEvents();
    
    // Actualizar filtros y estadísticas
    createFilters();
    updateStatsBar();
    
    showNotification(`Grafo actualizado: ${data.nodes.length} nodos, ${(data.links || []).length} enlaces`);
}

// Funciones de simulación
function ticked() {
    links
        .attr('x1', d => d.source.x)
        .attr('y1', d => d.source.y)
        .attr('x2', d => d.target.x)
        .attr('y2', d => d.target.y);
    
    nodes
        .attr('transform', d => `translate(${d.x},${d.y})`);
}

function dragstarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragended(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

// Inicializar autocomplete
function initAutocomplete() {
    autocomplete(document.getElementById('entity-search'), allEntities);
    autocomplete(document.getElementById('path-from'), allEntities);
    autocomplete(document.getElementById('path-to'), allEntities);
    autocomplete(document.getElementById('subgraph-entity'), allEntities);
}

// Función autocomplete mejorada
function autocomplete(inp, arr) {
    inp.addEventListener("input", function(e) {
        let a, b, i, val = this.value;
        closeAllLists();
        if (!val) { return false; }
        a = document.createElement("DIV");
        a.setAttribute("id", this.id + "-autocomplete-list");
        a.setAttribute("class", "autocomplete-items");
        this.parentNode.appendChild(a);
        
        // Filtrar entidades que coincidan
        const matches = arr.filter(item => 
            item.toLowerCase().includes(val.toLowerCase())
        ).slice(0, 10); // Limitar a 10 resultados
        
        for (i = 0; i < matches.length; i++) {
            b = document.createElement("DIV");
            const matchText = matches[i];
            const highlightIndex = matchText.toLowerCase().indexOf(val.toLowerCase());
            b.innerHTML = matchText.substring(0, highlightIndex) + 
                         "<strong>" + matchText.substring(highlightIndex, highlightIndex + val.length) + "</strong>" +
                         matchText.substring(highlightIndex + val.length);
            b.innerHTML += "<input type='hidden' value='" + matchText + "'>";
            b.addEventListener("click", function(e) {
                inp.value = this.getElementsByTagName("input")[0].value;
                closeAllLists();
            });
            a.appendChild(b);
        }
    });
    
    function closeAllLists(elmnt) {
        var x = document.getElementsByClassName("autocomplete-items");
        for (var i = 0; i < x.length; i++) {
            if (elmnt != x[i] && elmnt != inp) {
                x[i].parentNode.removeChild(x[i]);
            }
        }
    }
    
    document.addEventListener("click", function (e) {
        closeAllLists(e.target);
    });
}

// Selección de entidad y caja de preguntas
let selectedEntity = null;

function addNodeClickEvents() {
    nodes.on('click', function(event, d) {
        selectedEntity = d;
        
        // Mostrar caja de preguntas
        document.getElementById('qa-box').style.display = 'block';
        document.getElementById('llm-hint').style.display = 'none';
        document.getElementById('qa-response').style.display = 'none';
        document.getElementById('qa-question').value = '';
        
        // Auto-completar campos de navegación
        const pathFrom = document.getElementById('path-from');
        const pathTo = document.getElementById('path-to');
        const subgraphEntity = document.getElementById('subgraph-entity');
        
        // Si origen está vacío, poner la entidad como origen
        if (!pathFrom.value) {
            pathFrom.value = d.name;
        } 
        // Si origen está ocupado pero destino está vacío, poner como destino
        else if (!pathTo.value) {
            pathTo.value = d.name;
        }
        // Si ambos están ocupados, reemplazar destino
        else {
            pathTo.value = d.name;
        }
        
        // Poner como entidad para subgrafo
        subgraphEntity.value = d.name;
        
        // Mostrar notificación
        showNotification(`Entidad "${d.name}" seleccionada. Campos de navegación actualizados.`);
    });
}

// Función para mostrar notificaciones
function showNotification(message) {
    const notification = document.createElement('div');
    notification.className = 'position-fixed top-0 end-0 p-3';
    notification.style.zIndex = '9999';
    notification.innerHTML = `
        <div class="toast show" role="alert">
            <div class="toast-body">
                ${message}
            </div>
        </div>
    `;
    document.body.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 3000);
}

// Eventos de navegación
document.getElementById('search-btn').onclick = function() {
    const name = document.getElementById('entity-search').value;
    highlightAndCenterEntity(name);
};

function highlightAndCenterEntity(name) {
    // Buscar el nodo en todos los nodos originales
    const node = originalData.nodes.find(d => d.name.toLowerCase() === name.toLowerCase());
    if (!node) {
        showNotification('Entidad no encontrada.');
        return;
    }
    // Si el nodo no está visible, ajustar filtros para mostrarlo
    if (!currentFilters.entities.has(node.type)) {
        currentFilters.entities.add(node.type);
        createEntityFilters();
    }
    // Asegurarse de que el nodo esté en el grafo visible
    const visibleNode = nodes.data().find(d => d.id === node.id);
    if (!visibleNode) {
        // Reaplicar filtros y reconstruir grafo
        applyFiltersToGraph();
        setTimeout(() => highlightAndCenterEntity(name), 100); // Esperar a que se reconstruya
        return;
    }
    // Centrar en el nodo
    const transform = d3.zoomIdentity.translate(width/2 - visibleNode.x, height/2 - visibleNode.y);
    svg.transition().duration(750).call(d3.zoom().transform, transform);
    // Resaltar nodo
    nodes.select('circle').style('stroke', d => d.id === node.id ? '#e17055' : '#fff');
}

document.getElementById('path-btn').onclick = function() {
    const from = document.getElementById('path-from').value.trim();
    const to = document.getElementById('path-to').value.trim();
    
    if (!from || !to) {
        showNotification('Por favor, introduce ambas entidades para encontrar el camino.');
        return;
    }
    
    if (from.toLowerCase() === to.toLowerCase()) {
        showNotification('Las entidades de origen y destino no pueden ser las mismas.');
        return;
    }
    
    // Mostrar indicador de carga
    const pathBtn = document.getElementById('path-btn');
    const originalText = pathBtn.textContent;
    pathBtn.textContent = 'Buscando...';
    pathBtn.disabled = true;
    
    fetch(`/api/path?from=${encodeURIComponent(from)}&to=${encodeURIComponent(to)}`)
        .then(r => r.json())
        .then(data => {
            highlightPath(data.path);
        })
        .catch(error => {
            console.error('Error finding path:', error);
            showNotification('Error al buscar el camino entre entidades.');
        })
        .finally(() => {
            pathBtn.textContent = originalText;
            pathBtn.disabled = false;
        });
};

function highlightPath(pathData) {
    if (!pathData || !pathData.path || pathData.path.length === 0) {
        showNotification('No se encontró un camino entre las entidades especificadas.');
        return;
    }
    
    // Resetear estilos
    links.classed('highlighted', false);
    nodes.select('circle').style('stroke', '#fff');
    
    // Obtener los datos de los enlaces actuales
    const linkData = links.data();
    const relationshipIds = new Set(pathData.path);
    const highlightedLinks = new Set();
    const pathNodeIds = new Set();
    
    // Buscar enlaces que coincidan con los IDs de las relaciones del camino
    linkData.forEach((link, index) => {
        // Verificar si el enlace tiene un ID que coincida con los del camino
        if (link.id && relationshipIds.has(link.id)) {
            highlightedLinks.add(index);
            // Añadir nodos del camino
            if (typeof link.source === 'object') {
                pathNodeIds.add(link.source.id);
                pathNodeIds.add(link.target.id);
            } else {
                pathNodeIds.add(link.source);
                pathNodeIds.add(link.target);
            }
        }
    });
    
    // Si no encontramos coincidencias por ID, intentar por nombres de nodos
    if (highlightedLinks.size === 0 && pathData.relationships) {
        pathData.relationships.forEach(rel => {
            linkData.forEach((link, index) => {
                const sourceName = link.source_name || (typeof link.source === 'object' ? link.source.name : '');
                const targetName = link.target_name || (typeof link.target === 'object' ? link.target.name : '');
                
                if (sourceName === rel.source && targetName === rel.target) {
                    highlightedLinks.add(index);
                    // Añadir nodos del camino
                    if (typeof link.source === 'object') {
                        pathNodeIds.add(link.source.id);
                        pathNodeIds.add(link.target.id);
                    } else {
                        pathNodeIds.add(link.source);
                        pathNodeIds.add(link.target);
                    }
                }
            });
        });
    }
    
    // Resaltar enlaces
    links.classed('highlighted', (d, i) => highlightedLinks.has(i));
    
    // Resaltar nodos del camino
    nodes.select('circle').style('stroke', d => pathNodeIds.has(d.id) ? '#e17055' : '#fff');
    
    if (highlightedLinks.size > 0) {
        showNotification(`Camino resaltado: ${highlightedLinks.size} enlaces entre ${pathNodeIds.size} nodos`);
    } else {
        showNotification('No se pudo resaltar el camino encontrado. Los datos pueden no coincidir con el grafo actual.');
    }
}

document.getElementById('subgraph-btn').onclick = function() {
    const name = document.getElementById('subgraph-entity').value;
    const depth = document.getElementById('subgraph-depth').value;
    if (!name.trim()) {
        showNotification('Por favor, introduce el nombre de una entidad para el subgrafo.');
        return;
    }
    fetch(`/api/subgraph?name=${encodeURIComponent(name)}&depth=${depth}`)
        .then(r => r.json())
        .then(data => {
            updateGraphData(data);
        })
        .catch(error => {
            console.error('Error loading subgraph:', error);
            showNotification('Error al cargar el subgrafo.');
        });
};

document.getElementById('reset-btn').onclick = function() {
    loadGraph();
};

// Función para resetear filtros
function resetFilters() {
    // Resetear filtros a valores por defecto
    currentFilters.entities = new Set(['Person', 'Organization', 'Location', 'Date', 'Event', 'Object', 'Code']);
    currentFilters.relations = new Set(['explicit', 'inferred']);
    
    // Resetear categorías a todas las disponibles
    const categories = new Set();
    originalData.links.forEach(link => {
        if (link.category && link.category !== 'unknown') {
            categories.add(link.category);
        }
    });
    currentFilters.categories = new Set(categories);
    
    // Actualizar interfaz
    createFilters();
    applyFiltersToGraph();
    showNotification('Filtros reseteados');
}

// Pregunta al LLM enriquecida
document.getElementById('qa-submit').addEventListener('click', function() {
    if (!selectedEntity) return;
    const question = document.getElementById('qa-question').value;
    const depth = document.getElementById('subgraph-depth').value || 3;
    
    const responseDiv = document.getElementById('qa-response');
    responseDiv.style.display = 'block';
    responseDiv.innerHTML = '<div class="spinner-border spinner-border-sm" role="status"></div> Cargando respuesta...';
    
    // Obtener nodos y relaciones del grafo visible
    const visibleNodes = nodes.data().map(d => `${d.name} (${d.type})`);
    const visibleLinks = links.data().map(d => {
        const sourceName = d.source_name || d.source;
        const targetName = d.target_name || d.target;
        return `${sourceName} ${d.action} ${targetName} (${d.category || 'sin categoría'})`;
    });
    
    fetch('/api/ask_llm', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
            entity_id: selectedEntity.id, 
            question, 
            depth,
            visible_nodes: visibleNodes,
            visible_links: visibleLinks
        })
    })
    .then(r => r.json())
    .then(data => {
        responseDiv.innerHTML = data.response || data.error || 'Sin respuesta.';
    })
    .catch(error => {
        responseDiv.innerHTML = 'Error al obtener respuesta: ' + error.message;
    });
});

// Inicializar cuando se carga la página
window.addEventListener('load', initGraph);
</script>
</body>
</html>
    ''')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/graph')
def get_graph():
    try:
        # Obtener parámetros de filtro
        entity_types = request.args.getlist('entity_type')
        relation_types = request.args.getlist('relation_type')
        
        # Conectar a la base de datos
        graph_db = EntityGraph()
        
        # Verificar si hay datos en la base de datos
        with graph_db.driver.session() as session:
            # Contar entidades
            count_result = session.run("MATCH (e:Entity) RETURN count(e) as count")
            entity_count = count_result.single()["count"]
            
            if entity_count == 0:
                return jsonify({
                    "nodes": [],
                    "links": [],
                    "message": "La base de datos está vacía. Analiza un documento primero usando: python main.py --file/--url/--pdf <archivo> --store-db"
                })
        
        # Obtener datos del grafo con filtros
        graph_data = graph_db.get_entity_graph(limit=1000)
        
        # Aplicar filtros si se especifican
        if entity_types:
            graph_data['nodes'] = [node for node in graph_data['nodes'] 
                                 if node['type'] in entity_types]
        
        if relation_types:
            graph_data['links'] = [link for link in graph_data['links'] 
                                 if link.get('source', 'explicit') in relation_types]
        
        # --- PATCH: Ensure both keys exist and are lists ---
        if 'nodes' not in graph_data or not isinstance(graph_data['nodes'], list):
            graph_data['nodes'] = []
        if 'links' not in graph_data or not isinstance(graph_data['links'], list):
            graph_data['links'] = []
        
        # Añadir información sobre el estado de los datos
        if not graph_data['nodes']:
            graph_data['message'] = "No se encontraron entidades con los filtros aplicados"
        else:
            graph_data['message'] = f"Mostrando {len(graph_data['nodes'])} entidades y {len(graph_data['links'])} relaciones"
        
        return jsonify(graph_data)
        
    except Exception as e:
        return jsonify({
            'error': str(e),
            'message': 'Error al conectar con la base de datos. Asegúrate de que Neo4j esté corriendo.'
        }), 500

@app.route('/api/ask_llm', methods=['POST'])
def ask_llm():
    try:
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No se recibieron datos JSON'}), 400
            
        entity_id = data.get('entity_id')
        question = data.get('question')
        visible_nodes = data.get('visible_nodes', [])
        visible_links = data.get('visible_links', [])
        
        if not entity_id or not question:
            return jsonify({'error': 'Faltan parámetros entity_id o question'}), 400
        
        # Obtener subgrafo de nivel 3
        graph_db = EntityGraph()
        subgraph = graph_db.get_subgraph(entity_id, depth=3)
        
        # Construir prompt enriquecido para el LLM
        prompt = f"""
You are an expert OSINT analyst. The following is a subgraph (level 3) centered on a selected entity, extracted from a knowledge graph. The subgraph is provided as JSON with nodes and links, where each link includes a 'category' field. Answer the user's question using only the information in the subgraph.

User question: {question}

Subgraph JSON:
{subgraph}

Additionally, here are the entities and relationships currently visible in the graph interface:

Visible entities: {', '.join(visible_nodes) if visible_nodes else 'None'}

Visible relationships: {', '.join(visible_links) if visible_links else 'None'}

Responde la pregunta teniendo en cuenta que la información está organizada como un grafo de entidades y relaciones.
Pregunta: {question}
entidades: {', '.join(visible_nodes) if visible_nodes else 'None'}
relaciones: {', '.join(visible_links) if visible_links else 'None'}

Please provide a comprehensive answer based on the graph structure and relationships shown.
"""
        
        # Llamar al LLM real (usando tu pipeline, aquí ejemplo con Anthropic)
        from llm_providers import LLMProviderFactory
        provider = LLMProviderFactory.create_provider()
        
        # Crear mensaje en el formato correcto para el proveedor
        from langchain_core.messages import SystemMessage
        messages = [SystemMessage(content=prompt)]
        
        try:
            response = provider.generate_response(messages)
            return jsonify({'response': response})
        except Exception as e:
            logger.error(f"Error al consultar el LLM: {str(e)}")
            return jsonify({'error': f'Error al consultar el LLM: {str(e)}'}), 500
            
    except Exception as e:
        logger.error(f"Error en endpoint ask_llm: {str(e)}")
        return jsonify({'error': f'Error interno del servidor: {str(e)}'}), 500

@app.route('/api/entities')
def get_entities():
    graph_db = EntityGraph()
    names = graph_db.get_all_entity_names()
    return jsonify({'entities': names})

@app.route('/api/path')
def get_path():
    from_name = request.args.get('from')
    to_name = request.args.get('to')
    graph_db = EntityGraph()
    path = graph_db.get_shortest_path(from_name, to_name)
    return jsonify({'path': path})

@app.route('/api/subgraph')
def get_subgraph():
    name = request.args.get('name')
    depth = int(request.args.get('depth', 3))
    graph_db = EntityGraph()
    subgraph = graph_db.get_subgraph_by_name(name, depth)
    return jsonify(subgraph)

if __name__ == '__main__':
    # Usar configuración de Flask desde config.py
    app.run(
        host=AppConfig.FLASK_HOST,
        port=AppConfig.FLASK_PORT,
        debug=AppConfig.FLASK_DEBUG
    )