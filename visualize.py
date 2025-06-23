from flask import Flask, render_template, jsonify, request
from graph_database import EntityGraph
from config import AppConfig
import os

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
    <script src="https://cdnjs.cloudflare.com/ajax/libs/d3/7.8.5/d3.min.js"></script>
    <style>
        body, html { 
            margin: 0; 
            padding: 0;
            width: 100%;
            height: 100%;
            font-family: Arial, sans-serif;
        }
        #graph-container {
            width: 100%;
            height: 100vh;
            border: 1px solid #ccc;
            overflow: hidden;
            position: relative;
        }
        .node {
            cursor: pointer;
        }
        .node circle {
            stroke: #fff;
            stroke-width: 1.5px;
        }
        .link {
            stroke: #999;
            stroke-opacity: 0.6;
            stroke-width: 1px;
            fill: none;
        }
        .node-label {
            font-size: 12px;
            pointer-events: none;
        }
        .link-label {
            font-size: 10px;
            pointer-events: none;
            fill: #666;
        }
        .legend {
            position: absolute;
            top: 20px;
            right: 20px;
            background: white;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }
        .legend-item {
            margin: 5px 0;
        }
        .legend-color {
            display: inline-block;
            width: 15px;
            height: 15px;
            border-radius: 50%;
            margin-right: 5px;
        }
        .tooltip {
            position: absolute;
            background: white;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 8px;
            font-size: 12px;
            max-width: 300px;
        }
        .controls {
            position: absolute;
            top: 20px;
            left: 20px;
            background: white;
            padding: 10px;
            border: 1px solid #ccc;
            border-radius: 5px;
        }
        button {
            margin: 5px;
            padding: 5px 10px;
            cursor: pointer;
        }
        .filter-section {
            margin-top: 20px;
            border-top: 1px solid #ccc;
            padding-top: 10px;
        }
        .filter-group {
            margin: 10px 0;
        }
        .checkbox-group {
            display: flex;
            flex-direction: column;
        }
        .checkbox-group label {
            margin: 3px 0;
            display: flex;
            align-items: center;
        }
        .checkbox-group input {
            margin-right: 5px;
        }
        #apply-filters {
            display: block;
            margin-top: 10px;
            padding: 5px 15px;
            background-color: #4CAF50;
            color: white;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        #apply-filters:hover {
            background-color: #45a049;
        }
        .loading {
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 18px;
            color: #666;
            background: rgba(255, 255, 255, 0.8);
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
    </style>
</head>
<body>
    <div id="graph-container"></div>
    <div class="controls">
        <button id="zoom-in">Zoom In</button>
        <button id="zoom-out">Zoom Out</button>
        <button id="reset">Reset View</button>
        <div class="filter-section">
            <h3>Filtros</h3>
            <div class="filter-group">
                <label>Tipos de entidades:</label>
                <div class="checkbox-group">
                    <label><input type="checkbox" class="entity-type-filter" value="Person" checked> Personas</label>
                    <label><input type="checkbox" class="entity-type-filter" value="Organization" checked> Organizaciones</label>
                    <label><input type="checkbox" class="entity-type-filter" value="Location" checked> Lugares</label>
                    <label><input type="checkbox" class="entity-type-filter" value="Date" checked> Fechas</label>
                    <label><input type="checkbox" class="entity-type-filter" value="Event" checked> Eventos</label>
                    <label><input type="checkbox" class="entity-type-filter" value="Object" checked> Objetos</label>
                    <label><input type="checkbox" class="entity-type-filter" value="Code" checked> Códigos</label>
                </div>
            </div>
            <div class="filter-group">
                <label>Tipos de relaciones:</label>
                <div class="checkbox-group">
                    <label><input type="checkbox" class="relation-type-filter" value="explicit" checked> Explícitas</label>
                    <label><input type="checkbox" class="relation-type-filter" value="inferred" checked> Inferidas</label>
                </div>
            </div>
            <button id="apply-filters">Aplicar Filtros</button>
        </div>
    </div>
    <script>
        // Añade un evento para el botón de aplicar filtros
        document.getElementById('apply-filters').addEventListener('click', function() {
            loadGraphWithFilters();
        });
        
        // Función para cargar el grafo con filtros aplicados
        function loadGraphWithFilters() {
            // Recoger los filtros seleccionados
            const entityFilters = Array.from(document.querySelectorAll('.entity-type-filter:checked'))
                .map(checkbox => checkbox.value);
                
            const relationFilters = Array.from(document.querySelectorAll('.relation-type-filter:checked'))
                .map(checkbox => checkbox.value);
            
            // Construir la URL con parámetros de filtro
            let url = '/api/graph?';
            
            entityFilters.forEach(filter => {
                url += `entity_type=${filter}&`;
            });
            
            relationFilters.forEach(filter => {
                url += `relation_type=${filter}&`;
            });
            
            // Cargar el grafo con los filtros
            loadGraph(url);
        }
        
        // Variables globales para el grafo
        let svg, simulation, nodes, links;
        let width, height;
        
        // Función para inicializar el grafo
        function initGraph() {
            const container = document.getElementById('graph-container');
            width = container.clientWidth;
            height = container.clientHeight;
            
            // Crear SVG
            svg = d3.select('#graph-container')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            // Crear tooltip
            const tooltip = d3.select('body')
                .append('div')
                .attr('class', 'tooltip')
                .style('opacity', 0);
            
            // Crear simulación
            simulation = d3.forceSimulation()
                .force('link', d3.forceLink().id(d => d.id).distance(100))
                .force('charge', d3.forceManyBody().strength(-300))
                .force('center', d3.forceCenter(width / 2, height / 2));
            
            // Cargar datos iniciales
            loadGraph('/api/graph');
        }
        
        // Función para cargar el grafo
        function loadGraph(url = '/api/graph') {
            // Mostrar indicador de carga
            const loadingDiv = document.createElement('div');
            loadingDiv.className = 'loading';
            loadingDiv.textContent = 'Cargando grafo...';
            document.getElementById('graph-container').appendChild(loadingDiv);
            
            fetch(url)
            .then(response => response.json())
            .then(data => {
                // Remover indicador de carga
                document.querySelector('.loading').remove();
                
                // Verificar si hay mensaje de error o información
                if (data.message) {
                    // Mostrar mensaje informativo
                    const messageDiv = document.createElement('div');
                    messageDiv.className = 'loading';
                    messageDiv.style.textAlign = 'center';
                    messageDiv.style.maxWidth = '600px';
                    messageDiv.innerHTML = `
                        <h3>${data.message}</h3>
                        ${data.message.includes('vacía') ? `
                            <p><strong>Para empezar:</strong></p>
                            <ul style="text-align: left; display: inline-block;">
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
                    errorDiv.className = 'loading';
                    errorDiv.style.color = 'red';
                    errorDiv.innerHTML = `
                        <h3>Error</h3>
                        <p>${data.message || data.error}</p>
                    `;
                    document.getElementById('graph-container').appendChild(errorDiv);
                    return;
                }
                
                // Limpiar SVG existente
                svg.selectAll("*").remove();
                
                // Crear enlaces
                links = svg.append('g')
                    .selectAll('line')
                    .data(data.links)
                    .enter().append('line')
                    .attr('class', 'link');
            
                // Crear nodos
                nodes = svg.append('g')
                .selectAll('g')
                    .data(data.nodes)
                    .enter().append('g')
                    .attr('class', 'node')
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
                svg.append('g')
                    .selectAll('text')
                    .data(data.links)
                    .enter().append('text')
                .attr('class', 'link-label')
                    .text(d => d.action)
                    .attr('text-anchor', 'middle');
                
                // Actualizar simulación
                simulation
                    .nodes(data.nodes)
                    .on('tick', ticked);
                
                simulation.force('link')
                    .links(data.links);
                
                // Eventos de hover
                nodes.on('mouseover', function(event, d) {
                    tooltip.transition()
                        .duration(200)
                        .style('opacity', .9);
                    tooltip.html(`
                        <strong>${d.name}</strong><br/>
                        Tipo: ${d.type}<br/>
                        ${d.spanish ? 'Español: ' + d.spanish : ''}
                    `)
                        .style('left', (event.pageX + 5) + 'px')
                        .style('top', (event.pageY - 28) + 'px');
                })
                .on('mouseout', function(d) {
                    tooltip.transition()
                        .duration(500)
                        .style('opacity', 0);
                });
                
                // Crear leyenda
                createLegend();
                
            }).catch(error => {
                console.error('Error loading graph:', error);
                document.querySelector('.loading').remove();
                const errorDiv = document.createElement('div');
                errorDiv.className = 'loading';
                errorDiv.style.color = 'red';
                errorDiv.innerHTML = `
                    <h3>Error de conexión</h3>
                    <p>No se pudo cargar el grafo. Verifica que el servidor esté funcionando.</p>
                `;
                document.getElementById('graph-container').appendChild(errorDiv);
            });
        }
        
        // Función para crear leyenda
        function createLegend() {
            const legend = svg.append('g')
                .attr('class', 'legend')
                .attr('transform', `translate(${width - 150}, 20)`);
            
            const legendData = [
                {type: 'Person', color: '#ff6b6b'},
                {type: 'Organization', color: '#4ecdc4'},
                {type: 'Location', color: '#45b7d1'},
                {type: 'Date', color: '#96ceb4'},
                {type: 'Event', color: '#ff9ff3'},
                {type: 'Object', color: '#feca57'},
                {type: 'Code', color: '#54a0ff'}
            ];
            
            legend.selectAll('.legend-item')
                .data(legendData)
                .enter().append('g')
                .attr('class', 'legend-item')
                .attr('transform', (d, i) => `translate(0, ${i * 20})`)
                .each(function(d) {
                    d3.select(this).append('circle')
                        .attr('r', 6)
                        .style('fill', d.color);
                    
                    d3.select(this).append('text')
                        .attr('x', 15)
                        .attr('y', 4)
                        .text(d.type);
                });
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
        
        // Controles de zoom
        document.getElementById('zoom-in').addEventListener('click', function() {
            const currentScale = svg.attr('transform') ? 
                parseFloat(svg.attr('transform').match(/scale\(([^)]+)\)/)[1]) : 1;
            svg.attr('transform', `scale(${currentScale * 1.2})`);
        });
        
        document.getElementById('zoom-out').addEventListener('click', function() {
            const currentScale = svg.attr('transform') ? 
                parseFloat(svg.attr('transform').match(/scale\(([^)]+)\)/)[1]) : 1;
            svg.attr('transform', `scale(${currentScale / 1.2})`);
        });
        
        document.getElementById('reset').addEventListener('click', function() {
            svg.attr('transform', 'scale(1)');
            simulation.alpha(1).restart();
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
        graph_data = graph_db.get_entity_graph(limit=100)
        
        # Aplicar filtros si se especifican
        if entity_types:
            graph_data['nodes'] = [node for node in graph_data['nodes'] 
                                 if node['type'] in entity_types]
        
        if relation_types:
            graph_data['links'] = [link for link in graph_data['links'] 
                                 if link.get('source', 'explicit') in relation_types]
        
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

if __name__ == '__main__':
    # Usar configuración de Flask desde config.py
    app.run(
        host=AppConfig.FLASK_HOST,
        port=AppConfig.FLASK_PORT,
        debug=AppConfig.FLASK_DEBUG
    )