// Test script for diagram rendering
// Save as: frontend/test-diagram.js and run in browser console

(async function testDiagramRendering() {
    console.log("=== DIAGRAM RENDERING TEST ===");
    
    // Test 1: Check Cytoscape loaded
    console.log("\nTest 1: Cytoscape library loaded");
    if (typeof cytoscape !== 'undefined') {
        console.log("✅ Cytoscape available");
    } else {
        console.log("❌ Cytoscape NOT loaded");
        return;
    }
    
    // Test 2: Check API available
    console.log("\nTest 2: API functions available");
    const apiTests = [
        typeof loadDiagramData,
        typeof zoomIn,
        typeof zoomOut,
        typeof fitDiagram,
        typeof exportDiagram,
        typeof showFunctionDetails
    ];
    
    if (apiTests.every(t => t === 'function')) {
        console.log("✅ All diagram functions available");
    } else {
        console.log("❌ Some functions missing");
        console.log("  loadDiagramData:", typeof loadDiagramData);
        console.log("  zoomIn:", typeof zoomIn);
        console.log("  zoomOut:", typeof zoomOut);
        console.log("  fitDiagram:", typeof fitDiagram);
        console.log("  exportDiagram:", typeof exportDiagram);
        console.log("  showFunctionDetails:", typeof showFunctionDetails);
    }
    
    // Test 3: Check container exists
    console.log("\nTest 3: DOM elements");
    const container = document.getElementById('diagramContainer');
    if (container) {
        console.log("✅ Diagram container found");
        console.log("  Width:", container.offsetWidth);
        console.log("  Height:", container.offsetHeight);
    } else {
        console.log("❌ Diagram container NOT found");
    }
    
    // Test 4: Try loading diagram (if projectId set)
    console.log("\nTest 4: Load diagram data");
    if (typeof currentProjectId !== 'undefined' && currentProjectId) {
        try {
            const response = await fetch(`http://localhost:5000/api/diagram/project/${currentProjectId}/`);
            const data = await response.json();
            console.log("✅ Diagram data retrieved");
            console.log(`  Nodes: ${data.nodes.length}`);
            console.log(`  Edges: ${data.edges.length}`);
            console.log("  Sample node:", data.nodes[0]);
        } catch (error) {
            console.log("❌ Failed to load diagram data:", error);
        }
    } else {
        console.log("⚠️  No project selected - navigate to project first");
    }
    
    // Test 5: Check Cytoscape instance
    console.log("\nTest 5: Cytoscape instance");
    if (typeof cy !== 'undefined' && cy !== null) {
        console.log("✅ Cytoscape instance active");
        console.log("  Nodes:", cy.nodes().length);
        console.log("  Edges:", cy.edges().length);
    } else {
        console.log("⚠️  Cytoscape instance not initialized yet");
        console.log("   (Open a project to trigger loadDiagramData)");
    }
    
    // Test 6: Check localStorage
    console.log("\nTest 6: Session management");
    const user = localStorage.getItem('currentUser');
    if (user) {
        const userData = JSON.parse(user);
        console.log("✅ User session found in localStorage");
        console.log("  Username:", userData.username);
        console.log("  Role:", userData.role);
        console.log("  ID:", userData.id);
    } else {
        console.log("❌ No user session in localStorage");
    }
    
    console.log("\n=== TEST COMPLETE ===");
})();
