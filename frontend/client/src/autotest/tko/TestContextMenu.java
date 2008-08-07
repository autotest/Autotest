package autotest.tko;

import autotest.common.ui.ContextMenu;

import com.google.gwt.user.client.Command;

public class TestContextMenu extends ContextMenu {
    private static TestLabelManager labelManager = TestLabelManager.getManager();
    private TestSet tests;
    private TestSelectionListener listener;
    
    public TestContextMenu(TestSet tests, TestSelectionListener listener) {
        this.tests = tests;
        this.listener = listener;
    }
    
    public boolean addViewDetailsIfSingleTest() {
        if (!tests.isSingleTest()) {
            return false;
        }
        
        addItem("View test details", new Command() {
            public void execute() {
                TkoUtils.getTestId(tests, listener);
            }
        });
        return true;
    }
    
    public void addLabelItems() {
        addItem("Add label", new Command() {
            public void execute() {
                labelManager.handleAddLabels(tests.getCondition());
            }
        });
        addItem("Remove label", new Command() {
            public void execute() {
                labelManager.handleRemoveLabels(tests.getCondition());
            }
        });
    }
}
