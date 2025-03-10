from flask import Flask, render_template, jsonify, request
from graph_database import EntityGraph
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

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
            
            // Eliminar el contenedor del grafo actual
            d3.select("#graph-container svg").remove();
            
            // Mostrar indicador de carga
            const loading = d3.select("#graph-container")
                .append("div")
                .attr("class", "loading")
                .text("Cargando grafo...");
            
            // Cargar los datos filtrados
            fetch(url)
                .then(response => response.json())
                .then(data => {
                    loading.remove();
                    renderGraph(data);
                })
                .catch(error => {
                    loading.text("Error al cargar el grafo: " + error);
                    console.error('Error loading graph data:', error);
                });
        }
        
        // Modificar la carga inicial para usar la misma función
        document.addEventListener('DOMContentLoaded', function() {
            loadGraphWithFilters();
        });
        
        function renderGraph(data) {
            // Si no hay datos, mostrar mensaje
            if (!data.nodes || data.nodes.length === 0) {
                d3.select("#graph-container")
                    .append("div")
                    .attr("class", "loading")
                    .text("No hay datos para mostrar con los filtros seleccionados");
                return;
            }
            
            const container = document.getElementById('graph-container');
            const width = container.clientWidth;
            const height = container.clientHeight;
            
            // Create SVG
            const svg = d3.select('#graph-container')
                .append('svg')
                .attr('width', width)
                .attr('height', height);
            
            // Create tooltip
            const tooltip = d3.select('body')
                .append('div')
                .attr('class', 'tooltip')
                .style('opacity', 0);
            
            // Add zoom functionality
            const g = svg.append('g');
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', (event) => {
                    g.attr('transform', event.transform);
                });
                
            svg.call(zoom);
            
            // Zoom controls
            d3.select('#zoom-in').on('click', () => {
                svg.transition().call(zoom.scaleBy, 1.3);
            });
            
            d3.select('#zoom-out').on('click', () => {
                svg.transition().call(zoom.scaleBy, 0.7);
            });
            
            d3.select('#reset').on('click', () => {
                svg.transition().call(zoom.transform, d3.zoomIdentity);
            });
            
            // Handle missing UUID values
            data.nodes.forEach(node => {
                if (!node.id) {
                    node.id = 'node_' + Math.random().toString(36).substr(2, 9);
                }
            });
            
            data.relationships.forEach(rel => {
                if (!rel.source) {
                    rel.source = 'rel_source_' + Math.random().toString(36).substr(2, 9);
                }
                if (!rel.target) {
                    rel.target = 'rel_target_' + Math.random().toString(36).substr(2, 9);
                }
            });
            
            // Create force simulation
            const simulation = d3.forceSimulation(data.nodes)
                .force('link', d3.forceLink(data.relationships)
                    .id(d => d.id)
                    .distance(150))
                .force('charge', d3.forceManyBody().strength(-500))
                .force('center', d3.forceCenter(width / 2, height / 2))
                .force('collide', d3.forceCollide().radius(60));
            
            // Define entity type colors
            const typeColors = {
                'Person': '#5470C6',
                'Organization': '#91CC75',
                'Location': '#EE6666',
                'Date': '#73C0DE'
            };
            
            // Create legend
            const legend = svg.append('g')
                .attr('class', 'legend')
                .attr('transform', 'translate(' + (width - 150) + ',20)');
                
            const legendBg = legend.append('rect')
                .attr('width', 120)
                .attr('height', 110)
                .attr('fill', 'white')
                .attr('stroke', '#ccc')
                .attr('rx', 5);
                
            const legendTitle = legend.append('text')
                .attr('x', 10)
                .attr('y', 20)
                .text('Entity Types')
                .style('font-weight', 'bold');
                
            const legendItems = legend.selectAll('.legend-item')
                .data(Object.entries(typeColors))
                .enter()
                .append('g')
                .attr('class', 'legend-item')
                .attr('transform', (d, i) => 'translate(10,' + (i * 20 + 30) + ')');
                
            legendItems.append('circle')
                .attr('r', 6)
                .attr('fill', d => d[1]);
                
            legendItems.append('text')
                .attr('x', 15)
                .attr('y', 4)
                .text(d => d[0])
                .style('font-size', '12px');
            
            // Draw links
            const link = g.append('g')
                .selectAll('g')
                .data(data.relationships)
                .enter()
                .append('g');
            
            const path = link.append('path')
                .attr('class', 'link')
                .attr('stroke', d => d.type === 'inferred' ? '#d99' : '#999')  // Color diferente para relaciones inferidas
                .attr('stroke-dasharray', d => d.type === 'inferred' ? '5,5' : null)  // Línea punteada para inferidas
                .attr('stroke-width', d => d.type === 'inferred' ? '1px' : '1.5px')  // Línea más delgada para inferidas
                .attr('marker-end', 'url(#arrow)');
            
            // Add legend for relationship types
            const relLegend = svg.append('g')
                .attr('class', 'legend')
                .attr('transform', 'translate(' + (width - 150) + ',140)');
                
            const relLegendBg = relLegend.append('rect')
                .attr('width', 120)
                .attr('height', 70)
                .attr('fill', 'white')
                .attr('stroke', '#ccc')
                .attr('rx', 5);
                
            const relLegendTitle = relLegend.append('text')
                .attr('x', 10)
                .attr('y', 20)
                .text('Relationship Types')
                .style('font-weight', 'bold');
                
            // Relationship types legend
            const relTypes = [
                {name: 'Explicit', color: '#999', dashed: false},
                {name: 'Inferred', color: '#d99', dashed: true}
            ];

            const relLegendItems = relLegend.selectAll('.rel-legend-item')
                .data(relTypes)
                .enter()
                .append('g')
                .attr('class', 'legend-item')
                .attr('transform', (d, i) => 'translate(10,' + (i * 20 + 30) + ')');
                
            relLegendItems.append('line')
                .attr('x1', 0)
                .attr('y1', 0)
                .attr('x2', 20)
                .attr('y2', 0)
                .attr('stroke', d => d.color)
                .attr('stroke-width', 2)
                .attr('stroke-dasharray', d => d.dashed ? '3,3' : null);
                
            relLegendItems.append('text')
                .attr('x', 25)
                .attr('y', 4)
                .text(d => d.name)
                .style('font-size', '12px');
                
            const linkLabels = link.append('text')
                .attr('class', 'link-label')
                .attr('dy', -5)
                .append('textPath')
                .attr('xlink:href', (d, i) => '#linkPath' + i)
                .attr('startOffset', '50%')
                .attr('text-anchor', 'middle')
                .text(d => d.action);
            
            // Draw nodes
            const node = g.append('g')
                .selectAll('g')
                .data(data.nodes)
                .enter()
                .append('g')
                .attr('class', 'node')
                .on('mouseover', function(event, d) {
                    tooltip.transition()
                        .duration(200)
                        .style('opacity', .9);
                    
                    let content = `<strong>${d.name}</strong><br/>`;
                    content += `Type: ${d.type}<br/>`;
                    if (d.spanish) {
                        content += `Spanish: ${d.spanish}<br/>`;
                    }
                    
                    tooltip.html(content)
                        .style('left', (event.pageX + 10) + 'px')
                        .style('top', (event.pageY - 28) + 'px');
                })
                .on('mouseout', function() {
                    tooltip.transition()
                        .duration(500)
                        .style('opacity', 0);
                })
                .call(d3.drag()
                    .on('start', dragStarted)
                    .on('drag', dragged)
                    .on('end', dragEnded));
            
            // Add circles to nodes
            node.append('circle')
                .attr('r', 15)
                .attr('fill', d => typeColors[d.type] || '#999');
            
            // Add labels to nodes
            node.append('text')
                .attr('class', 'node-label')
                .attr('dx', 20)
                .attr('dy', 4)
                .text(d => d.name);
            
            // Set up simulation ticks
            simulation.on('tick', () => {
                // Update link paths
                path.attr('d', d => {
                    const dx = d.target.x - d.source.x;
                    const dy = d.target.y - d.source.y;
                    const dr = Math.sqrt(dx * dx + dy * dy);
                    
                    // Calculate position for the middle of the link for label placement
                    d.labelX = d.source.x + dx / 2;
                    d.labelY = d.source.y + dy / 2;
                    
                    return 'M' + d.source.x + ',' + d.source.y + 'A' + dr + ',' + dr + ' 0 0,1 ' + d.target.x + ',' + d.target.y;
                })
                .attr('id', (d, i) => 'linkPath' + i);
                
                // Update link labels
                linkLabels.attr('x', d => d.labelX)
                    .attr('y', d => d.labelY);
                
                // Update node positions
                node.attr('transform', d => 'translate(' + d.x + ',' + d.y + ')');
            });
            
            // Drag functions
            function dragStarted(event, d) {
                if (!event.active) simulation.alphaTarget(0.3).restart();
                d.fx = d.x;
                d.fy = d.y;
            }
            
            function dragged(event, d) {
                d.fx = event.x;
                d.fy = event.y;
            }
            
            function dragEnded(event, d) {
                if (!event.active) simulation.alphaTarget(0);
                d.fx = null;
                d.fy = null;
            }
        }
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
        # Obtener parámetros de filtro de la consulta
        entity_types = request.args.getlist('entity_type')
        relation_types = request.args.getlist('relation_type')
        show_inferred = request.args.get('show_inferred', 'true').lower() == 'true'
        
        graph_db = EntityGraph()
        
        # Construir la consulta de nodos con filtros dinámicos
        entity_filter_clause = ""
        if entity_types:
            entity_types_quoted = [f"'{t}'" for t in entity_types]
            entity_filter_clause = f"WHERE e.type IN [{', '.join(entity_types_quoted)}]"
        
        nodes_query = f"""
            MATCH (e:Entity)
            {entity_filter_clause}
            RETURN e.uuid AS id, e.name AS name, e.type AS type, e.spanish AS spanish
            LIMIT 500
        """
        
        with graph_db.driver.session() as session:
            # Obtener nodos filtrados
            result_nodes = session.run(nodes_query)
            
            nodes = [
                {
                    "id": record["id"],
                    "name": record["name"],
                    "type": record["type"],
                    "spanish": record["spanish"]
                }
                for record in result_nodes
            ]
            
            # IDs de los nodos filtrados para usarlos en consultas de relaciones
            node_ids = [node["id"] for node in nodes]
            
            # Si no hay nodos, devolver grafo vacío
            if not node_ids:
                return jsonify({"nodes": [], "relationships": []})
            
            # Construir consultas de relaciones
            relationships = []
            
            # Relaciones explícitas
            if not relation_types or 'explicit' in relation_types:
                explicit_query = f"""
                    MATCH (s:Entity)-[r:RELATES_TO]->(o:Entity)
                    WHERE s.uuid IN $node_ids AND o.uuid IN $node_ids
                    RETURN s.uuid AS source, o.uuid AS target, r.action AS action, 'explicit' AS rel_type
                    LIMIT 1000
                """
                explicit_rels = session.run(explicit_query, node_ids=node_ids)
                
                relationships.extend([
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "action": record["action"],
                        "type": record["rel_type"]
                    }
                    for record in explicit_rels
                ])
            
            # Relaciones inferidas
            if show_inferred and (not relation_types or 'inferred' in relation_types):
                inferred_query = f"""
                    MATCH (s:Entity)-[r:INFERRED]->(o:Entity)
                    WHERE s.uuid IN $node_ids AND o.uuid IN $node_ids
                    RETURN s.uuid AS source, o.uuid AS target, r.action AS action, 'inferred' AS rel_type
                    LIMIT 1000
                """
                inferred_rels = session.run(inferred_query, node_ids=node_ids)
                
                relationships.extend([
                    {
                        "source": record["source"],
                        "target": record["target"],
                        "action": record["action"],
                        "type": record["rel_type"]
                    }
                    for record in inferred_rels
                ])
        
        graph_db.close()
        
        return jsonify({
            "nodes": nodes,
            "relationships": relationships
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)