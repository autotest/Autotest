package afeclient.client.table;

import afeclient.client.JsonRpcProxy;
import afeclient.client.JsonRpcCallback;
import afeclient.client.Utils;

import com.google.gwt.json.client.JSONArray;
import com.google.gwt.json.client.JSONNumber;
import com.google.gwt.json.client.JSONObject;
import com.google.gwt.json.client.JSONString;
import com.google.gwt.json.client.JSONValue;

/**
 * Data source that retrieves results via RPC requests to the server.
 */
public class RpcDataSource implements DataSource {
    protected String getDataMethod, getCountMethod;
    protected JSONObject filterParams;
    protected Integer numResults = null;
    
    public RpcDataSource(String getDataMethod, String getCountMethod) {
        this.getDataMethod = getDataMethod;
        this.getCountMethod = getCountMethod;
    }
    
    /**
     * Process the JSON result returned by the server into an array of result 
     * objects.  This default implementation assumes the result itself is an array.
     * Subclasses may override this to construct an array from the JSON result.
     */
    protected JSONArray handleJsonResult(JSONValue result) {
        return result.isArray();
    }
    
    public void updateData(JSONObject params, final DataCallback callback) {
        filterParams = params;
        JsonRpcProxy.getProxy().rpcCall(getCountMethod, params, 
                                        new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                int count = (int) result.isNumber().getValue();
                numResults = new Integer(count);
                callback.onGotData(count);
            }    
        });
    }

    public void getPage(Integer start, Integer maxCount, 
                        String sortOn, Integer sortDirection, 
                        final DataCallback callback) {
        JSONObject params;
        if (filterParams == null)
            params = new JSONObject();
        else
            params = Utils.copyJSONObject(filterParams);
        if (start != null)
            params.put("query_start", new JSONNumber(start.intValue()));
        if (maxCount != null)
            params.put("query_limit", new JSONNumber(maxCount.intValue()));
        if (sortOn != null) {
            if (sortDirection.intValue() == DataSource.DESCENDING)
                sortOn = "-" + sortOn;
            JSONArray sortList = new JSONArray();
            sortList.set(0, new JSONString(sortOn));
            params.put("sort_by", sortList);
        }
        
        JsonRpcProxy.getProxy().rpcCall(getDataMethod, params, 
                                        new JsonRpcCallback() {
            public void onSuccess(JSONValue result) {
                JSONArray resultData = handleJsonResult(result);
                callback.handlePage(resultData);
            } 
        });
    }

    public int getNumResults() {
        assert numResults != null;
        return numResults.intValue();
    }
}
