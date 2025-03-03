from flask import Flask, render_template, jsonify
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
    </style>
</head>
<body>
    <div id="graph-container"></div>
    <div class="controls">
        <button id="zoom-in">Zoom In</button>
        <button id="zoom-out">Zoom Out</button>
        <button id="reset">Reset View</button>
    </div>
    <script>
        // Fetch graph data from API
        fetch('/api/graph')
            .then(response => response.json())
            .then(data => renderGraph(data))
            .catch(error => console.error('Error loading graph data:', error));
        
        function renderGraph(data) {
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
                .attr('stroke', '#999')
                .attr('marker-end', 'url(#arrow)');
                
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
        graph_db = EntityGraph()
        graph_data = graph_db.get_entity_graph(limit=200)  # Aumentado el límite para ver más entidades
        graph_db.close()
        return jsonify(graph_data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)