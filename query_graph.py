#!/usr/bin/env python3
"""
Utilidad para consultar y filtrar la base de datos Neo4j.
Este script permite ejecutar consultas personalizadas y filtrar entidades y relaciones.
"""

import argparse
import sys
import logging
import json
from tabulate import tabulate
from graph_database import EntityGraph
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def list_entity_types(graph_db):
    """Lista todos los tipos de entidades disponibles con conteo."""
    with graph_db.driver.session() as session:
        result = session.run("""
            MATCH (e:Entity)
            RETURN e.type AS type, count(e) AS count
            ORDER BY count DESC
        """)
        
        types = [(record["type"], record["count"]) for record in result]
        
        print("\n=== Tipos de Entidades ===")
        print(tabulate(types, headers=["Tipo", "Cantidad"], tablefmt="pretty"))

def list_entities_by_type(graph_db, entity_type):
    """Lista todas las entidades de un tipo específico."""
    with graph_db.driver.session() as session:
        result = session.run("""
            MATCH (e:Entity)
            WHERE e.type = $type
            RETURN e.name AS name, e.spanish AS spanish, 
                   size((e)-[:RELATES_TO]->()) + size((e)<-[:RELATES_TO]-()) AS explicit_relations,
                   size((e)-[:INFERRED]->()) + size((e)<-[:INFERRED]-()) AS inferred_relations
            ORDER BY explicit_relations + inferred_relations DESC
            LIMIT 50
        """, type=entity_type)
        
        entities = [(
            record["name"], 
            record["spanish"] or "-", 
            record["explicit_relations"],
            record["inferred_relations"],
            record["explicit_relations"] + record["inferred_relations"]
        ) for record in result]
        
        print(f"\n=== Entidades de tipo: {entity_type} (top 50) ===")
        print(tabulate(entities, 
                      headers=["Nombre", "Español", "Rel. Explícitas", "Rel. Inferidas", "Total Rel."], 
                      tablefmt="pretty"))

def list_documents(graph_db):
    """Lista todos los documentos analizados."""
    with graph_db.driver.session() as session:
        result = session.run("""
            MATCH (d:Document)
            OPTIONAL MATCH (e:Entity)-[:MENTIONED_IN]->(d)
            RETURN d.title AS title, d.analysisDate AS date, d.source_url AS url,
                   count(DISTINCT e) AS entities
            ORDER BY date DESC
        """)
        
        docs = [(
            record["title"], 
            record["date"], 
            record["url"] or "-",
            record["entities"]
        ) for record in result]
        
        print("\n=== Documentos Analizados ===")
        print(tabulate(docs, headers=["Título", "Fecha", "URL", "Entidades"], tablefmt="pretty"))

def get_entity_relationships(graph_db, entity_name, show_inferred=True):
    """Muestra todas las relaciones de una entidad específica."""
    with graph_db.driver.session() as session:
        # Buscar entidad por nombre (puede haber múltiples con el mismo nombre pero tipo diferente)
        entity_result = session.run("""
            MATCH (e:Entity)
            WHERE e.name = $name
            RETURN e.name AS name, e.type AS type, e.uuid AS id
        """, name=entity_name)
        
        entities = [record for record in entity_result]
        
        if not entities:
            print(f"No se encontró ninguna entidad con el nombre '{entity_name}'")
            return
        
        if len(entities) > 1:
            print(f"\nSe encontraron múltiples entidades con el nombre '{entity_name}':")
            for i, entity in enumerate(entities):
                print(f"{i+1}. {entity['name']} ({entity['type']})")
            
            # Solicitar al usuario que elija una entidad
            choice = input("\nSeleccione el número de la entidad que desea consultar: ")
            try:
                idx = int(choice) - 1
                if idx < 0 or idx >= len(entities):
                    print("Selección inválida")
                    return
                entity = entities[idx]
            except ValueError:
                print("Entrada inválida")
                return
        else:
            entity = entities[0]
        
        print(f"\n=== Relaciones para: {entity['name']} ({entity['type']}) ===\n")
        
        # Relaciones donde la entidad es sujeto
        outgoing_result = session.run("""
            MATCH (e:Entity {uuid: $id})-[r:RELATES_TO]->(o:Entity)
            RETURN 'outgoing' AS direction, o.name AS name, o.type AS type, r.action AS action, 'explicit' AS rel_type
            UNION
            MATCH (e:Entity {uuid: $id})-[r:INFERRED]->(o:Entity)
            RETURN 'outgoing' AS direction, o.name AS name, o.type AS type, r.action AS action, 'inferred' AS rel_type
        """, id=entity['id'])
        
        # Relaciones donde la entidad es objeto
        incoming_result = session.run("""
            MATCH (s:Entity)-[r:RELATES_TO]->(e:Entity {uuid: $id})
            RETURN 'incoming' AS direction, s.name AS name, s.type AS type, r.action AS action, 'explicit' AS rel_type
            UNION
            MATCH (s:Entity)-[r:INFERRED]->(e:Entity {uuid: $id})
            RETURN 'incoming' AS direction, s.name AS name, s.type AS type, r.action AS action, 'inferred' AS rel_type
        """, id=entity['id'])
        
        # Combinar resultados
        relationships = []
        
        for record in outgoing_result:
            if record["rel_type"] == "inferred" and not show_inferred:
                continue
            relationships.append([
                "→",
                record["name"],
                record["type"],
                record["action"],
                record["rel_type"]
            ])
        
        for record in incoming_result:
            if record["rel_type"] == "inferred" and not show_inferred:
                continue
            relationships.append([
                "←",
                record["name"],
                record["type"], 
                record["action"],
                record["rel_type"]
            ])
        
        if relationships:
            print(tabulate(
                sorted(relationships, key=lambda x: (x[4] != 'explicit', x[0], x[2], x[1])),
                headers=["Dir", "Entidad", "Tipo", "Acción", "Tipo Rel"],
                tablefmt="pretty"
            ))
        else:
            print("No se encontraron relaciones para esta entidad")

def find_path_between_entities(graph_db, source_name, target_name, max_length=4):
    """Encuentra caminos entre dos entidades."""
    with graph_db.driver.session() as session:
        # Buscar entidades por nombre
        source_result = session.run("""
            MATCH (e:Entity)
            WHERE e.name = $name
            RETURN e.name AS name, e.type AS type, e.uuid AS id
        """, name=source_name)
        
        target_result = session.run("""
            MATCH (e:Entity)
            WHERE e.name = $name
            RETURN e.name AS name, e.type AS type, e.uuid AS id
        """, name=target_name)
        
        sources = [record for record in source_result]
        targets = [record for record in target_result]
        
        if not sources:
            print(f"No se encontró ninguna entidad con el nombre '{source_name}'")
            return
        
        if not targets:
            print(f"No se encontró ninguna entidad con el nombre '{target_name}'")
            return
        
        print(f"\n=== Buscando caminos de '{source_name}' a '{target_name}' (max {max_length} saltos) ===\n")
        
        # Para cada combinación de fuente/destino, buscar caminos
        paths_found = False
        
        for source in sources:
            for target in targets:
                if source['id'] == target['id']:
                    continue
                
                path_result = session.run("""
                    MATCH path = shortestPath((s:Entity {uuid: $source_id})-[*1..%d]-(t:Entity {uuid: $target_id}))
                    RETURN path, length(path) as path_length
                    ORDER BY path_length
                    LIMIT 5
                """ % max_length, source_id=source['id'], target_id=target['id'])
                
                paths = [record for record in path_result]
                
                if paths:
                    paths_found = True
                    print(f"Caminos de {source['name']} ({source['type']}) a {target['name']} ({target['type']}):")
                    
                    for i, record in enumerate(paths):
                        path = record["path"]
                        nodes = path.nodes
                        relationships = path.relationships
                        
                        print(f"\n  Camino {i+1} (longitud: {record['path_length']}):")
                        
                        for j in range(len(nodes) - 1):
                            start_node = nodes[j]
                            end_node = nodes[j+1]
                            rel = relationships[j]
                            
                            rel_type = "INFERRED" if rel.type == "INFERRED" else "RELATES_TO"
                            
                            print(f"    {start_node['name']} ({start_node['type']}) --[{rel['action']} ({rel_type})]-> {end_node['name']} ({end_node['type']})")
        
        if not paths_found:
            print(f"No se encontraron caminos entre '{source_name}' y '{target_name}' con máximo {max_length} saltos")

def search_entities(graph_db, search_term):
    """Busca entidades por nombre."""
    with graph_db.driver.session() as session:
        result = session.run("""
            MATCH (e:Entity)
            WHERE toLower(e.name) CONTAINS toLower($term) OR 
                  toLower(e.spanish) CONTAINS toLower($term)
            RETURN e.name AS name, e.type AS type, e.spanish AS spanish,
                   size((e)-[:RELATES_TO]->()) + size((e)<-[:RELATES_TO]-()) +
                   size((e)-[:INFERRED]->()) + size((e)<-[:INFERRED]-()) AS total_relations
            ORDER BY total_relations DESC
            LIMIT 30
        """, term=search_term)
        
        entities = [(
            record["name"],
            record["type"],
            record["spanish"] or "-",
            record["total_relations"]
        ) for record in result]
        
        print(f"\n=== Entidades que contienen '{search_term}' ===")
        
        if entities:
            print(tabulate(entities, 
                          headers=["Nombre", "Tipo", "Español", "Total Rel."], 
                          tablefmt="pretty"))
        else:
            print(f"No se encontraron entidades que contengan '{search_term}'")

def export_graph(graph_db, filename, include_inferred=True):
    """Exporta el grafo completo a un archivo JSON."""
    with graph_db.driver.session() as session:
        # Obtener todos los nodos
        nodes_result = session.run("""
            MATCH (e:Entity)
            RETURN e.uuid AS id, e.name AS name, e.type AS type, e.spanish AS spanish
        """)
        
        nodes = [
            {
                "id": record["id"],
                "name": record["name"],
                "type": record["type"],
                "spanish": record["spanish"]
            }
            for record in nodes_result
        ]
        
        # Obtener todas las relaciones explícitas
        explicit_rels_result = session.run("""
            MATCH (s:Entity)-[r:RELATES_TO]->(o:Entity)
            RETURN s.uuid AS source, o.uuid AS target, r.action AS action, 'explicit' AS rel_type
        """)
        
        relationships = [
            {
                "source": record["source"],
                "target": record["target"],
                "action": record["action"],
                "type": record["rel_type"]
            }
            for record in explicit_rels_result
        ]
        
        # Si se incluyen relaciones inferidas, obtenerlas también
        if include_inferred:
            inferred_rels_result = session.run("""
                MATCH (s:Entity)-[r:INFERRED]->(o:Entity)
                RETURN s.uuid AS source, o.uuid AS target, r.action AS action, 'inferred' AS rel_type
            """)
            
            relationships.extend([
                {
                    "source": record["source"],
                    "target": record["target"],
                    "action": record["action"],
                    "type": record["rel_type"]
                }
                for record in inferred_rels_result
            ])
        
        # Crear el objeto de grafo
        graph_data = {
            "nodes": nodes,
            "relationships": relationships
        }
        
        # Guardar a archivo
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(graph_data, f, ensure_ascii=False, indent=2)
        
        print(f"\nGrafo exportado a {filename}")
        print(f"Nodos: {len(nodes)}")
        print(f"Relaciones: {len(relationships)}")

def main():
    parser = argparse.ArgumentParser(
        description="Consulta y filtra la base de datos Neo4j de entidades y relaciones"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")
    
    # Comando: listar tipos de entidades
    list_types_parser = subparsers.add_parser("list-types", help="Listar todos los tipos de entidades")
    
    # Comando: listar entidades por tipo
    list_entities_parser = subparsers.add_parser("list-entities", help="Listar entidades por tipo")
    list_entities_parser.add_argument("type", help="Tipo de entidad")
    
    # Comando: listar documentos
    list_docs_parser = subparsers.add_parser("list-docs", help="Listar documentos analizados")
    
    # Comando: obtener relaciones de una entidad
    get_rels_parser = subparsers.add_parser("get-relations", help="Obtener relaciones de una entidad")
    get_rels_parser.add_argument("entity", help="Nombre de la entidad")
    get_rels_parser.add_argument("--no-inferred", action="store_true", 
                               help="No mostrar relaciones inferidas")
    
    # Comando: buscar caminos entre entidades
    find_path_parser = subparsers.add_parser("find-path", help="Encontrar caminos entre dos entidades")
    find_path_parser.add_argument("source", help="Entidad origen")
    find_path_parser.add_argument("target", help="Entidad destino")
    find_path_parser.add_argument("--max-length", type=int, default=4, 
                                help="Longitud máxima del camino (por defecto: 4)")
    
    # Comando: buscar entidades
    search_parser = subparsers.add_parser("search", help="Buscar entidades por nombre")
    search_parser.add_argument("term", help="Término de búsqueda")
    
    # Comando: exportar grafo
    export_parser = subparsers.add_parser("export", help="Exportar grafo a archivo JSON")
    export_parser.add_argument("filename", help="Nombre del archivo de salida")
    export_parser.add_argument("--no-inferred", action="store_true", 
                             help="No incluir relaciones inferidas")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    try:
        # Conectar a la base de datos
        graph_db = EntityGraph()
        
        # Ejecutar el comando correspondiente
        if args.command == "list-types":
            list_entity_types(graph_db)
        
        elif args.command == "list-entities":
            list_entities_by_type(graph_db, args.type)
        
        elif args.command == "list-docs":
            list_documents(graph_db)
        
        elif args.command == "get-relations":
            get_entity_relationships(graph_db, args.entity, not args.no_inferred)
        
        elif args.command == "find-path":
            find_path_between_entities(graph_db, args.source, args.target, args.max_length)
        
        elif args.command == "search":
            search_entities(graph_db, args.term)
        
        elif args.command == "export":
            export_graph(graph_db, args.filename, not args.no_inferred)
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
    
    finally:
        if 'graph_db' in locals():
            graph_db.close()

if __name__ == "__main__":
    main()